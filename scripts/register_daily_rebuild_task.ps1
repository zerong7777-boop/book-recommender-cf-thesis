param(
  [string]$ProjectRoot = "E:\projects\book-recommender-cf",
  [string]$CondaEnv = "bookrec311",
  [string]$TaskName = "BookRecommenderDailyRebuild",
  [string]$DailyAt = "02:00",
  [string]$SettingsModule = "book_recommender.settings"
)

$ErrorActionPreference = "Stop"

$conda = (Get-Command conda).Source
$action = New-ScheduledTaskAction `
  -Execute $conda `
  -Argument "run -n $CondaEnv python manage.py rebuild_recommendations --settings=$SettingsModule" `
  -WorkingDirectory $ProjectRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $DailyAt
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger $trigger `
  -Principal $principal `
  -Description "Daily offline recommendation rebuild for the Book Recommender thesis demo." `
  -Force

Write-Host "Registered scheduled task '$TaskName' at $DailyAt using settings '$SettingsModule'."
