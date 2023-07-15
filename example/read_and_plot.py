"""Read data from purdue_plot.py every minute and use it to make a plot."""
import csv
import os
import time
from datetime import datetime, timedelta

import matplotlib.pyplot as plt


DATA_IN_DIR = 'data'
PLOT_OUT = 'data'


def get_time_to_minute(hour_offset: int = 0) -> datetime:
    """Return the UTC time right now without seconds or milli/microseconds.

    Optionally offset by hour_offset hours. Meaning, if hour_offset = 2, return
    the UTC time from 2 hours ago without seconds or microseconds.
    """
    tyme = datetime.utcnow()
    return tyme - timedelta(hours=hour_offset, seconds=tyme.second,
                            microseconds=tyme.microsecond)


def set_up_plot() -> None:
    """Set up the plot."""
    ax = plt.gca()
    ax.set_box_aspect(0.5)
    ax.set_facecolor('black')
    ax.grid(visible=True, which='major', color='gray', linestyle='-', lw=0.2)
    ax.set_ylim([0, 250])

    plt.title('RSU1 SBT')
    plt.xlabel('Time of Day (PDT)')
    plt.ylabel('Cycle Time (seconds)')


def plot_xticks(start_time: datetime, end_time: datetime) -> None:
    """Plot x ticks."""
    ax = plt.gca()

    first_loc = int((start_time - timedelta(
        minutes=start_time.minute,
        seconds=start_time.second
    )).timestamp())

    extra_hour = 0 if end_time.minute == 0 and end_time.second == 0 else 1
    last_loc = int((end_time + timedelta(hours=extra_hour) - timedelta(
        minutes=end_time.minute,
        seconds=end_time.second
    )).timestamp())

    if start_time.hour == end_time.hour and start_time.day == end_time.day:
        last_loc += 3600

    ax.set_xlim([first_loc, last_loc])

    # Make x ticks to only be at each hour
    x_ticks = list(range(first_loc, last_loc + 1, 3600))

    # Assign x labels, converted to PDT from UTC
    x_labels = [(datetime.fromtimestamp(x_val)
                 + timedelta(hours=-7)).strftime('%#I:%M %p\n%B %#d')
                for x_val in x_ticks]

    # Plot xticks
    ax.set_xticks(x_ticks, x_labels, fontsize='xx-small', rotation=45,
                  ha='center')


def main():
    """Execute the script."""
    set_up_plot()
    start_time = get_time_to_minute()
    tyme = start_time
    prev_time = tyme - timedelta(minutes=1)

    while True:
        try:
            # If tyme == prev_time, they are from the same minute, since both
            # don't include seconds/microseconds
            if tyme == prev_time:
                tyme = get_time_to_minute()
                continue

            # Wait for Purdue plot output; should only take a few seconds but
            # using 30 seconds for safety
            time.sleep(30)

            for fname in ('green_lines.csv', 'red_lines.csv', 'dots.csv'):
                x, y = [], []
                with open(os.path.join(DATA_IN_DIR, fname), 'r', newline='',
                          encoding='utf-8') as file:
                    reader = csv.reader(file)
                    next(reader)  # Skip header

                    for row in reader:
                        # Only care about RSU1 WBT here
                        if row[:3] == ['1', 'WB', 'T']:
                            x.append(float(row[3]))
                            y.append(float(row[4]))

                    if fname[0] == 'd':
                        plt.scatter(x, y, c='white', s=2, alpha=0.5)
                    else:
                        plt.plot(x, y, c=fname.split('_')[0], marker='')

            prev_time = tyme
            tyme = get_time_to_minute(1)

        except KeyboardInterrupt:
            break

    print('Ctrl-C detected; Building plots... Do not hit Ctrl-C')
    # Plot from an hour back, since purdue_plot.py collects data from an hour
    # back
    plot_xticks(start_time - timedelta(hours=1), tyme)
    plt.tight_layout()
    plt.savefig(PLOT_OUT)


if __name__ == '__main__':
    main()
