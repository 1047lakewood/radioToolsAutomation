' Hidden launcher for radioToolsAutomation
' Runs the application without showing a console window

Dim args, appPath, batFile
Set args = WScript.Arguments

' Get the batch file path from command line argument
If args.Count > 0 Then
    batFile = args(0)
Else
    ' Default to START RDS AND INTRO.bat in the same directory as this script
    appPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
    batFile = appPath & "START RDS AND INTRO.bat"
End If

' Create WScript Shell object
Set objShell = CreateObject("WScript.Shell")

' Run the batch file hidden (0 = hidden, False = don't wait)
objShell.Run batFile, 0, False

' Exit silently
WScript.Quit
