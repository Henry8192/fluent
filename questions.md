# Fluentd: Questions to Answer

Assume there is a long-running process that always writes logs into one file,
1. How does Fluentd monitor the file changes?
>  Fluentd uses `pos_file` to handle multiple positions in one file.
It tracks the file change and record the lines it accessed last time before it closed.

2. How does Fluentd track the file status and send logs into S3?
  
3. What is the file format on the S3 end?

4. The file system does not strictly lock system read/write events. This means when Fluentd (as a reader) reads the file, the log generator (as the writer) can write to the same file simultaneously. Does Fluentd handle this situation? Is it guaranteed that everything being uploaded is a complete log message and it will never cut one message in half?
> It is worth noticing that Fluentd chooses to do nothing if the logs specified to be monitored are not initially created. Fluentd would not detect these logs until you reload the application.
However, if the file is initially created, Fluentd would start to record the change of that file. Need to dig to source code of `tail` input plugin.
  

5. Log rotation (e.g., https://www.blog.pythonlibrary.org/2014/02/11/python-how-to-create-rotating-logs/) is common in log files. How does Fluentd handle log file renaming?
> The following log provides a hint of how Fluentd handles rotation:
`detected rotation of ./log/input.log; waiting 5 seconds`
need to dig down to source code of `tail`.

6. If either: a) Fluentd crashes; b) the system or the log generator crashes, when everything is successfully rebooted, how does Fluentd resume the state before crashes? What states are tracked by Fluentd? In general, how does Fluentd handle crash recovery?
> If Fluentd crashes but the log keeps generating, Fluentd would try to visit the updated log and ship it to s3. 
