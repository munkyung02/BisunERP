Option Explicit

Dim shell, fileSystem
Dim projectDirectory, logDirectory
Dim pythonExecutable, mainScript, logFile
Dim command

projectDirectory = "C:\BisunERP_v2.8"
logDirectory = projectDirectory & "\logs"
pythonExecutable = "C:\Users\USER\AppData\Local\Programs\Python\Python314\python.exe"
mainScript = projectDirectory & "\main.py"
logFile = logDirectory & "\bisun_erp_launcher.log"

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

If Not fileSystem.FolderExists(logDirectory) Then
    fileSystem.CreateFolder(logDirectory)
End If

shell.CurrentDirectory = projectDirectory

command = "%ComSpec% /D /S /C """ _
    & """" & pythonExecutable & """ " _
    & "-u " _
    & """" & mainScript & """" _
    & " >> """ & logFile & """ 2>&1"""

shell.Run command, 0, False
