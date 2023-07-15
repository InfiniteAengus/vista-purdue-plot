# purdue_plot
This code writes Purdue coordination diagram data points to <code>data/</code> every minute.

# Output
Each minute, the files in the <code>data/</code> folder are overwritten with data points for the Purdue plot collected in the last minute. The files are <code>green_lines.csv</code>, <code>yellow_lines.csv</code>, <code>red_lines.csv</code>, and <code>dots.csv</code>.  
Each file has the columns <code>RSU</code>, <code>Bound</code>, <code>Movement</code>, <code>x</code>, and <code>y</code>, as well as columns that translate <code>x</code> into human-readable UTC, PST, and PDT time strings.  
Example output is located at <code>example_output/</code>. Note that it is only one minute of data, since the data is overwritten each minute.

# Utilizing the Output
The output in <code>data/</code> should be used directly to make the Purdue coordination diagrams on way-logic.com.  
The method that has worked for me to plot the data is as follows:
* Start <code>purdue_plot.py</code>.
* Wait until the time has a second value of exactly 30 seconds, such as 02:15:30.00 and unlike 02:16:00.000.
  * <code>purdue_plot.py</code> begins to overwrite the files in <code>data/</code> at times with a second value of exactly 0. Waiting until a time with a second value of 30 essentially gives <code>purdue_plot.py</code> 30 seconds to write to <code>data/</code>. It should only take a few seconds, but I used 30 seconds to be safe.
  * It may be easier to wait until a time has a second value of exactly 0 seconds, and then waiting for 30 seconds (this is actually what I did).
* Read the files in <code>data/</code> (except for <code>yellow_lines.csv</code>), and simply use the <code>x</code> and <code>y</code> columns as data point values. Plot on the correct plot, which can be found with the <code>RSU</code>, <code>Bound</code>, and <code>Movement</code> columns.
* Repeat from Step 2.  

I have provided the code I used to plot in <code>example_utilize/</code>. Note that it is in Python and I was only focusing on RSU1 WBT movement.

# Changes from Previous Code
* Removed code for Python plot output
* Data overwritten every minute, rather than appended
* Added PST time strings to data
