"""Make Purdue coordination diagram from cycle and event data."""
import csv
import json
import math
import os
import pathlib
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import requests

from objects import Location, Point, TLColor


WINDOWS = sys.platform == 'win32'
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
ENCODING = 'utf-8'

DATA_OUT_DIR = os.path.join(SCRIPT_DIR, 'data')
GREEN_OUT_FILE = os.path.join(DATA_OUT_DIR, 'green_lines.csv')
YELLOW_OUT_FILE = os.path.join(DATA_OUT_DIR, 'yellow_lines.csv')
RED_OUT_FILE = os.path.join(DATA_OUT_DIR, 'red_lines.csv')
EVENT_OUT_FILE = os.path.join(DATA_OUT_DIR, 'dots.csv')
COLOR_TO_OUT_FILE = {TLColor.GREEN: GREEN_OUT_FILE,
                     TLColor.YELLOW: YELLOW_OUT_FILE,
                     TLColor.RED: RED_OUT_FILE}
DATA_HEADER = ['RSU', 'Bound', 'Movement', 'x', 'y', 'x as UTC Time',
               'x as PST Time', 'x as PDT Time', 'x as 12-Hr PST Time',
               'x as 12-Hr PDT Time']

CYCLES_API_URL = ('https://hcub010205.execute-api.us-east-2.amazonaws.com'
                  '/vista/spat')
TRAFFIC_API_URL = ('https://hcub010205.execute-api.us-east-2.amazonaws.com'
                   '/vista/traffic')

CYCLE_TIME_FMT = '%Y-%m-%d %H:%M:%S.%f'
URL_TIME_FMT = '%Y-%m-%d %H:%M:%S'
PLOT_DATA_TIME_FMT = CYCLE_TIME_FMT
PLOT_DATA_12HR_TIME_FMT = '%Y-%m-%d %I:%M:%S.%f %p'
UTC_TO_PDT = -7  # UTC is 7 hours ahead of PDT
UTC_TO_PST = -8  # UTC is 8 hours ahead of PST
HOUR_LAG = 1  # Go 1 hour back when fetching data

CycleDataType = Dict[Location, List[Dict[TLColor, Optional[datetime]]]]
ControllerEventsType = Dict[Location, List[datetime]]
StoredCyclePointsType = Dict[Location, Dict[TLColor, List[Point]]]
StoredEventsType = Dict[Location, List[List[float]]]


def make_dir(dir_: str) -> None:
    r"""Make the directory.

    Examples:
    fname="three/two/" -> Make the directory three/two
    fname="three/two" -> Make the directory three/two

    The slashes are dependent on platform. On Mac and Linux it is /, while on
    Windows it is \.
    """
    pathlib.Path(dir_).mkdir(parents=True, exist_ok=True)


def get_time_to_minute(hour_offset: int = 0) -> datetime:
    """Return the UTC time right now without seconds or milli/microseconds.

    Optionally offset by hour_offset hours. Meaning, if hour_offset = 2, return
    the UTC time from 2 hours ago without seconds or microseconds.
    """
    tyme = datetime.utcnow()
    return tyme - timedelta(hours=hour_offset, seconds=tyme.second,
                            microseconds=tyme.microsecond)


def get_cycle_message(session: requests.Session, tyme: datetime) -> Dict:
    """Get a message from the cycles API."""
    url = f'{CYCLES_API_URL}?timestamp={tyme.strftime(URL_TIME_FMT)}'
    return json.loads(session.get(url).text)


def get_traffic_message(session: requests.Session, tyme: datetime) -> Dict:
    """Get a message from the traffic API."""
    url = f'{TRAFFIC_API_URL}?timestamp={tyme.strftime(URL_TIME_FMT)}'
    return json.loads(session.get(url).text)


def write_header(fname: str) -> None:
    """Write header to file.

    Create the file if it doesn't exist. Truncate if it does exist.
    """
    with open(fname, 'w', newline='', encoding=ENCODING) as file:
        csv.writer(file).writerow(DATA_HEADER)


def make_cycle_data(cycle_msg: Dict) -> CycleDataType:
    """Make cycle data from message."""
    data: CycleDataType = defaultdict(list)
    if 'statusCode' not in cycle_msg or cycle_msg['statusCode'] != 200:
        return data

    for rsu, bound_dict in cycle_msg['body'].items():
        for bound, mvmt_dict in bound_dict.items():
            for mvmt, color_dict in mvmt_dict.items():
                datum = {color: None if not color_dict[color.value]
                         else datetime.strptime(color_dict[color.value],
                                                CYCLE_TIME_FMT)
                         for color in TLColor}
                if any(datum.values()):
                    data[Location(int(rsu), bound, mvmt)].append(datum)

    return data


def get_controller_events(traffic_msg: Dict, tyme: datetime
                          ) -> ControllerEventsType:
    """Return list of controller events from traffic message."""
    events: ControllerEventsType = defaultdict(list)
    if 'statusCode' not in traffic_msg or traffic_msg['statusCode'] != 200:
        return events

    for rsu_id, bound_mvmt_triggers in traffic_msg['body'].items():
        for bound, mvmt_triggers in bound_mvmt_triggers.items():
            for mvmt, trigger_dict in mvmt_triggers.items():
                for trigger in trigger_dict['trigger_time'].split(','):
                    if trigger:
                        events[Location(int(rsu_id), bound, mvmt)].append(
                            tyme + timedelta(seconds=float(trigger))
                        )

    return events


def update_stored_cycle_points(stored_cycle_points: StoredCyclePointsType,
                               all_cycle_data: CycleDataType) -> None:
    """Update stored cycle data points with new cycle data."""
    for loc, data in all_cycle_data.items():
        for datum in data:
            curr_cycle_points: Dict[TLColor, Point] = {}

            # Maintain GYR order
            for color in TLColor:
                tyme = datum[color]

                prev_point: Optional[Point] = (
                    None if not stored_cycle_points[loc][color]
                    else stored_cycle_points[loc][color][-1]
                )
                prev_red_point: Optional[Point] = (
                    None if not stored_cycle_points[loc][TLColor.RED]
                    else stored_cycle_points[loc][TLColor.RED][-1]
                )

                # If no data for this color in this cycle or previous cycle,
                # then no point for it yet
                if tyme is None and prev_point is None:
                    continue

                # If no data for this color in this cycle and we have data for
                # this color at the last cycle, just use that
                if tyme is None and prev_point is not None:
                    curr_cycle_points[color] = prev_point

                # If this is the first time we have data for this color, just
                # use its seconds as y value
                elif prev_point is None:
                    curr_cycle_points[color] = Point(tyme.timestamp(),
                                                     tyme.second)

                # If we have a red start time from previous cycle, use that to
                # make y value for this green time
                elif color == TLColor.GREEN:
                    curr_cycle_points[color] = Point(tyme.timestamp(),
                                                     tyme.timestamp()
                                                     - prev_red_point.x)

                # If there's a green in this cycle, use that to make y value
                # for this yellow time
                elif (color == TLColor.YELLOW
                        and TLColor.GREEN in curr_cycle_points):
                    curr_cycle_points[color] = Point(
                        tyme.timestamp(),
                        curr_cycle_points[TLColor.GREEN].y + tyme.timestamp()
                        - curr_cycle_points[TLColor.GREEN].x
                    )

                # If there's a yellow in this cycle, use that to make y value
                # for this red time
                elif (color == TLColor.RED
                        and TLColor.YELLOW in curr_cycle_points):
                    curr_cycle_points[color] = Point(
                        tyme.timestamp(),
                        curr_cycle_points[TLColor.YELLOW].y + tyme.timestamp()
                        - curr_cycle_points[TLColor.YELLOW].x
                    )

                # If there's a green in this cycle, use that to make y value
                # for this red time
                elif (color == TLColor.RED
                        and TLColor.GREEN in curr_cycle_points):
                    curr_cycle_points[color] = Point(
                        tyme.timestamp(),
                        curr_cycle_points[TLColor.GREEN].y + tyme.timestamp()
                        - curr_cycle_points[TLColor.GREEN].x
                    )

                # Else, just use seconds
                else:
                    curr_cycle_points[color] = Point(tyme.timestamp(),
                                                     tyme.second)

                stored_cycle_points[loc][color].append(
                    curr_cycle_points[color]
                )
                if len(stored_cycle_points[loc][color]) == 4:
                    stored_cycle_points[loc][color].pop(0)


def update_stored_events(stored_events: StoredEventsType,
                         all_new_events: ControllerEventsType) -> None:
    """Update stored events with new data."""
    for loc, events in all_new_events.items():
        if len(stored_events[loc]) == 3:
            stored_events[loc].pop(0)
        stored_events[loc].append([event.timestamp() for event in events])


def make_data_row(loc: Location, x_val: float, y_val: float
                  ) -> List[Union[str, float, int]]:
    """Make and return data row."""
    utc = datetime.fromtimestamp(x_val)
    pst = utc + timedelta(hours=UTC_TO_PST)
    pdt = utc + timedelta(hours=UTC_TO_PDT)
    return [loc.rsu_id, loc.bound, loc.movement, x_val, y_val,
            utc.strftime(PLOT_DATA_TIME_FMT), pst.strftime(PLOT_DATA_TIME_FMT),
            pdt.strftime(PLOT_DATA_TIME_FMT),
            pst.strftime(PLOT_DATA_12HR_TIME_FMT),
            pdt.strftime(PLOT_DATA_12HR_TIME_FMT)]


def write_cycle_data(stored_cycle_points: StoredCyclePointsType) -> None:
    """Write cycle data."""
    for fname in COLOR_TO_OUT_FILE.values():
        write_header(fname)

    for loc, stored_points in stored_cycle_points.items():
        for color, points in stored_points.items():
            if len(points) < 2:
                continue

            x_vals = [points[-2].x, points[-1].x]
            y_vals = [points[-2].y, points[-1].y]

            with open(COLOR_TO_OUT_FILE[color], 'a', newline='',
                      encoding=ENCODING) as file:
                writer = csv.writer(file)
                for x_val, y_val in zip(x_vals, y_vals):
                    writer.writerow(make_data_row(loc, x_val, y_val))


def write_events(stored_events: StoredEventsType,
                 stored_cycle_points: StoredCyclePointsType) -> None:
    """Write events."""
    write_header(EVENT_OUT_FILE)

    for loc, all_events in stored_events.items():
        if (len(all_events) < 3
                or len(stored_cycle_points[loc][TLColor.RED]) < 3):
            continue

        x_vals, y_vals = [], []
        # Only interested in writing events from 2 minutes ago right now
        for event in sorted(all_events[0]):
            diff = float('inf')
            for point in stored_cycle_points[loc][TLColor.RED]:
                if 0 <= event - point.x < diff:
                    diff = event - point.x

            if not math.isinf(diff):
                x_vals.append(event)
                y_vals.append(diff)

        with open(EVENT_OUT_FILE, 'a', newline='', encoding=ENCODING) as file:
            writer = csv.writer(file)
            for x_val, y_val in zip(x_vals, y_vals):
                writer.writerow(make_data_row(loc, x_val, y_val))


def main():
    """Execute the program."""
    # Make directories
    make_dir(DATA_OUT_DIR)

    stored_cycle_points: StoredCyclePointsType = defaultdict(
        lambda: defaultdict(list)
    )
    stored_events: StoredEventsType = defaultdict(list)
    session = requests.Session()

    start_time = get_time_to_minute(HOUR_LAG)
    tyme = start_time
    prev_time = start_time - timedelta(minutes=1)

    while True:
        try:
            if tyme == prev_time:
                tyme = get_time_to_minute(HOUR_LAG)
                continue

            # Get new data
            cycle_data = make_cycle_data(get_cycle_message(session, tyme))
            events = get_controller_events(get_traffic_message(session, tyme),
                                           tyme)

            # Update stored cycle and event data
            update_stored_cycle_points(stored_cycle_points, cycle_data)
            update_stored_events(stored_events, events)

            # Plot cycles from now
            write_cycle_data(stored_cycle_points)

            # Plot events from 2 minutes ago
            write_events(stored_events, stored_cycle_points)

            prev_time = tyme
            tyme = get_time_to_minute(HOUR_LAG)

        # Stop on Ctrl-C
        except KeyboardInterrupt:
            break

    print('Ctrl-C detected; Exiting')


if __name__ == '__main__':
    main()
