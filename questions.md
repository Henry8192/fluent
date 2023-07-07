# Fluentd: Questions to Answer
## 20230602
Assume there is a long-running process that always writes logs into one file,
#### 1. How does Fluentd monitor the file changes?

Fluentd uses `pos_file` to handle multiple positions in one file.
It tracks the file change and record the lines it accessed last time before it closed.
```
    pos               inode
    ffffffffffffffff\tffffffffffffffff\n
```

#### 2. How does Fluentd track the file status and send logs into S3?
  
### 3. What is the file format on the S3 end?

#### 4. The file system does not strictly lock system read/write events. This means when Fluentd (as a reader) reads the file, the log generator (as the writer) can write to the same file simultaneously. Does Fluentd handle this situation? Is it guaranteed that everything being uploaded is a complete log message and it will never cut one message in half?

It is worth noticing that Fluentd chooses to do nothing if the logs specified to be monitored are not initially created. Fluentd would not detect these logs until you reload the application.
However, if the file is initially created, Fluentd would start to record the change of that file. Need to dig to source code of `tail` input plugin.
  

#### 5. Log rotation (e.g., https://www.blog.pythonlibrary.org/2014/02/11/python-how-to-create-rotating-logs/) is common in log files. How does Fluentd handle log file renaming?

The following log provides a hint of how Fluentd handles rotation:
`detected rotation of ./log/input.log; waiting 5 seconds`
need to dig down to source code of `tail`.

#### 6. If either: a) Fluentd crashes; b) the system or the log generator crashes, when everything is successfully rebooted, how does Fluentd resume the state before crashes? What states are tracked by Fluentd? In general, how does Fluentd handle crash recovery?

If Fluentd crashes but the log keeps generating, Fluentd would try to visit the updated log and ship it to s3. 

## 20230610
#### 1. We need to know how to monitor a log directory

`fluent.conf` uses regex to match files in a path. For example, you can use `./log/*` to match all the files in the log subfolder, but the use of `./log/` would cause fluentd to raise errors.

however, in_tail with '\*' path doesn't check rotation file equality at refresh phase.
So you should not use '\*' path when your logs will be rotated by another tool.
It will cause log duplication after updated watch files.
In such case, you should separate log directory and specify two paths in path parameter.
e.g. path /path/to/dir/*,/path/to/rotated_logs/target_file

#### 2a) how is log rotation detected? 

[fluentd log rotation detection](https://github.com/fluent/fluentd/issues/2692)
Check `in_tail.rb`. Fluentd tracks the file's inode and file size, and if inode changes or the file size becomes smaller, fluentd identifies the log rotation. It also uses timer and inotify-based watcher to check file status.
From the explanation above, it is possible that a file is changed but its size is even bigger than the previous record, and Fluentd would not detect the log rotation. However, my educated guess is Fluentd polls frequently so this issue can be avoided.

#### 2b) Why we need to wait for 5 seconds?

It simply wants to avoid the intermediate state. The waiting time is arbitrarily set to 5 seconds and can be modifed by changing `rotate_wait`.

#### 3. What does Fluentd parse from the raw log? Can we do integration?

[How to Write Parser Plugin](https://docs.fluentd.org/plugin-development/api-plugin-parser)

#### 4. When the file is rotated, how does Fluentd make sure the file chunk is fully synchronized (guarantee the old file is completely uploaded)
1. Waiting for a specified duration: When a rotation of a log file is detected, the code includes a waiting period of @rotate_wait seconds before updating the watcher. This waiting period allows time for the file rotation process to complete and for any remaining log data to be written to the old file. The purpose of this wait is to give the old file time to be fully synchronized and avoid any potential data loss.

2. Throttling and reading all contents: If throttling is enabled (based on the `throttling_is_enabled?` method), the code ensures that all the contents of the file are read before closing it. This ensures that the old file is completely read and synchronized before proceeding. It waits until the watcher reaches the end of the file (`tw.eof?`) and the elapsed time since the rotation is equal to or greater than `@rotate_wait` seconds. Only then is the watcher detached.

3. Closing the watcher only after synchronization: The `detach_watcher_after_rotate_wait` method waits for the specified rotation wait time or until the watcher reaches the end of the file before detaching the watcher. This ensures that the watcher remains attached and continues reading the file until it is fully synchronized, guaranteeing that the old file is completely uploaded before closing it.

#### 5. Take more time looking at the crash-recovery behavior

##### Scenario 1: Fluentd crashes
Steps:
1. Open Fluentd, monitor a rotating log file, make sure the targeted log file is created but empty (otherwise fluentd would not detect the creation of the file)
2. Open log generator
3. When logs are rotating, `pkill fluentd` and let the logs rotates for a while
4. Open fluentd again, let it continues to collect logs

##### Observation:
Fluentd fails to sync logs during the crash, as we can see the missing message_id between 226349 and 435431. This is expected since there's no way to track these rotating logs if Fluentd is down. Notice that the fluentd log messages are complete.
When Fluentd is reopened, it successfully discovers that the logs are rotated, and correctly tracks the logging messages.
The concole output after fluentd encounters log rotation:
```log
2023-06-14 18:31:12 +0800 [warn]: #0 Skip update_watcher because watcher has been already updated by other inotify event path="./log/input.log" inode=5804634 inode_in_pos_file=5804644
2023-06-14 18:31:12 +0800 [info]: #0 detected rotation of ./log/input.log; waiting 5 seconds
2023-06-14 18:31:12 +0800 [warn]: #0 Skip update_watcher because watcher has been already updated by other inotify event path="./log/input.log" inode=5804647 inode_in_pos_file=5804644
2023-06-14 18:31:12 +0800 [info]: #0 detected rotation of ./log/input.log; waiting 5 seconds
2023-06-14 18:31:12 +0800 [warn]: #0 Skip update_watcher because watcher has been already updated by other inotify event path="./log/input.log" inode=5804642 inode_in_pos_file=5804644
2023-06-14 18:31:12 +0800 [info]: #0 detected rotation of ./log/input.log; waiting 5 seconds
2023-06-14 18:31:12 +0800 [info]: #0 following tail of ./log/input.log
2023-06-14 18:31:12 +0800 [info]: #0 detected rotation of ./log/input.log; waiting 5 seconds
2023-06-14 18:31:12 +0800 [warn]: #0 Skip update_watcher because watcher has been already updated by other inotify event path="./log/input.log" inode=5804644 inode_in_pos_file=5804645
2023-06-14 18:31:12 +0800 [info]: #0 detected rotation of ./log/input.log; waiting 5 seconds
```

##### Scenario 2: Operating System Crashes
Similar to scenario 1, but change the `pkill fluentd` in step 3 to `sudo shutdown -h now`
Reboot the operating system, see what happens.

##### Observation:
Open the buffer folder `./out` and see the buffered output. Notice that the last line is incomplete:

```log
2023-06-14T19:18:10+08:00	test	{"message":"2023-06-14 19:18:10,718 INFO root generate_logs: message_id<195621> This is a log message with one spark unique app id per line: app-20230614 621-15621 from spark-node-621"}
2023-06-14T19:18:10+08:00	test	{"message":"2023-06-14 19:18:
```

The actual `input.log` is up to message_id<195634>, and the last message is complete.

After rebooting the system and reopening Fluentd, two output files are generated, and the log messages are overlapping. The first output log still contains this incomplete message, while the second log recopies the contents in `input.log`.

The second test shows similar behaviors, buffered logs contains incomplete messages and the output files overlaps one another.
```log
2023-06-14T20:18:20+08:00	test	{"message":"2023-06-14 20:18:20,002 INFO root generate_logs: message_id<356579> This is a log message with one spark unique app id per line: app-20230614 579-16579 from spark-node-579"}
2023-06-14T20:18:20+08:00	test	{"message":"2023-06-14 20:18:20,002 INFO root generate_logs: message_id<356580> This is a log message with one spark unique app id per line: app-20230614 5
```

However, this time the second output file goes back to only 10 messages before:
```log
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,001 INFO root generate_logs: message_id<356570> This is a log message with one spark unique app id per line: app-20230614 570-16570 from spark-node-570"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,001 INFO root generate_logs: message_id<356571> This is a log message with one spark unique app id per line: app-20230614 571-16571 from spark-node-571"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,001 INFO root generate_logs: message_id<356572> This is a log message with one spark unique app id per line: app-20230614 572-16572 from spark-node-572"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,001 INFO root generate_logs: message_id<356573> This is a log message with one spark unique app id per line: app-20230614 573-16573 from spark-node-573"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,001 INFO root generate_logs: message_id<356574> This is a log message with one spark unique app id per line: app-20230614 574-16574 from spark-node-574"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,001 INFO root generate_logs: message_id<356575> This is a log message with one spark unique app id per line: app-20230614 575-16575 from spark-node-575"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,001 INFO root generate_logs: message_id<356576> This is a log message with one spark unique app id per line: app-20230614 576-16576 from spark-node-576"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,001 INFO root generate_logs: message_id<356577> This is a log message with one spark unique app id per line: app-20230614 577-16577 from spark-node-577"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,001 INFO root generate_logs: message_id<356578> This is a log message with one spark unique app id per line: app-20230614 578-16578 from spark-node-578"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,002 INFO root generate_logs: message_id<356579> This is a log message with one spark unique app id per line: app-20230614 579-16579 from spark-node-579"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,002 INFO root generate_logs: message_id<356580> This is a log message with one spark unique app id per line: app-20230614 580-16580 from spark-node-580"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,002 INFO root generate_logs: message_id<356581> This is a log message with one spark unique app id per line: app-20230614 581-16581 from spark-node-581"}
2023-06-14T20:36:06+08:00	test	{"message":"2023-06-14 20:18:20,002 INFO root generate_logs: message_id<356582> This is a log message with one spark unique app id per line: app-20230614 582-16582 from spark-node-582"}
```

Notice that the log generator also crashes and contains some garbage at the end of file, but Fluentd somehow avoids these garbage data and did not log them into the output files.

The third test holds the same result as the first test.

##### 20230707 Observation
Previous OS tests are not valid.
