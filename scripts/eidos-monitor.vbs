Option Explicit
Dim shell, files, runner, command, quote
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
quote = Chr(34)
runner = files.BuildPath(files.GetParentFolderName(WScript.ScriptFullName), "eidos-monitor.cmd")
command = quote & shell.ExpandEnvironmentStrings("%ComSpec%") & quote & " /d /c " & quote & quote & runner & quote & quote
shell.Run command, 0, False
