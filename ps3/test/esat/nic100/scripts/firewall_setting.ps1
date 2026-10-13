# 允许执行任何脚本
Set-ExecutionPolicy Unrestricted
# 安裝添加WinRM IIS Extsion功能。
Import-Module ServerManager
Add-WindowsFeature WinRM-IIS-Ext
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
Get-Service sshd
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force
$credential = Import-Clixml -Path "C:\Users\Administrator\sxetest\credential.xml"
write-host "$credential = Import-Clixml -Path "C:\Users\Administrator\sxetest\credential.xml""