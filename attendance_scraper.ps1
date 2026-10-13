# ============================================================
# 曙光(SOA)考勤系统 —— 自动登录 + 抓取脚本 (PowerShell 版)
# 在【能访问公司内网】的 Windows 机器上运行:
#   powershell -ExecutionPolicy Bypass -File .\attendance_scraper.ps1
# ============================================================

$ErrorActionPreference = "Stop"

# ---------------- 配置区 ----------------
$Username   = "weiyuan1"
$Password   = "Sugon@1234"
$LoginUrl   = "https://soa.com.cn/oaataticsv/attendance/index.html"
$AttendUrl  = "https://soa.com.cn/oaataticsv/attendance/index.html"
$BaseUrl    = "https://soa.com.cn"
$OutputDir  = Join-Path $PSScriptRoot "output"
$TimeoutSec = 30

# 手动兜底字段名(若自动识别失败, 打开登录页 F12 查看 input 的 name 后填在这里)
$UserFieldName  = $null   # 例如 "loginName"
$PassFieldName  = $null   # 例如 "passWord"

# 内网自签名证书常见, 设为 $true 跳过证书校验
$SkipCertCheck = $true

if (-not (Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir | Out-Null }

function Log($msg) {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg)
}

function Save-Text($path, $text) {
    [System.IO.File]::WriteAllText($path, $text, [System.Text.Encoding]::UTF8)
    Log "已保存: $path"
}

# ---------------- TLS / 证书 ----------------
try {
    if ($SkipCertCheck) {
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    }
    [System.Net.ServicePointManager]::SecurityProtocol = `
        [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls11 -bor [System.Net.SecurityProtocolType]::Tls
} catch {
    Log "警告: 设置 TLS 失败, 继续尝试: $_"
}

# ---------------- 步骤1: 获取登录页 ----------------
Log "访问登录页: $LoginUrl"
try {
    $loginResp = Invoke-WebRequest -Uri $LoginUrl -SessionVariable webSession -TimeoutSec $TimeoutSec -UseBasicParsing
} catch {
    Log "请求失败: $_"
    exit 1
}

Log "登录页状态码: $($loginResp.StatusCode)"
$loginHtml = $loginResp.Content
Save-Text (Join-Path $OutputDir "debug_login_page.html") $loginHtml

# ---------------- 步骤2: 解析表单(正则提取 input) ----------------
$inputs = [regex]::Matches($loginHtml, '<input[^>]*>') | ForEach-Object { $_.Value }
Log "页面共发现 $($inputs.Count) 个 input"

function Get-InputAttr($inputTag, $attr) {
    $m = [regex]::Match($inputTag, "$attr\s*=\s*[`"']([^`"']*)[`"']", "IgnoreCase")
    if ($m.Success) { return $m.Groups[1].Value } else { return $null }
}

function Find-InputByKeys($inputs, $keys) {
    foreach ($t in $inputs) {
        $name  = Get-InputAttr $t "name"
        $id    = Get-InputAttr $t "id"
        $ph    = Get-InputAttr $t "placeholder"
        $blob  = ("$name $id $ph").ToLower()
        foreach ($k in $keys) {
            if ($blob.Contains($k)) { return $t }
        }
    }
    return $null
}

$userKeys = @("username","user_name","loginname","login_name","j_username","account","userid","user_id","user","emp","empcode","emp_code","workno","work_no","jobnumber","job_number","loginid","login_id","staff","email")
$passKeys = @("password","passwd","pwd","j_password","userpassword","user_password","loginpwd","login_pwd")

$userInput = Find-InputByKeys $inputs $userKeys
$passInput = Find-InputByKeys $inputs $passKeys

if ($UserFieldName) { $userField = $UserFieldName }
elseif ($userInput)  { $userField = (Get-InputAttr $userInput "name"); if (-not $userField) { $userField = (Get-InputAttr $userInput "id") } }
else                 { $userField = $null }

if ($PassFieldName) { $passField = $PassFieldName }
elseif ($passInput)  { $passField = (Get-InputAttr $passInput "name"); if (-not $passField) { $passField = (Get-InputAttr $passInput "id") } }
else                 { $passField = $null }

Log "识别到用户名字段: $userField"
Log "识别到密码字段: $passField"

if (-not $userField -or -not $passField) {
    Log "[失败] 无法自动识别登录字段, 请手动设置脚本顶部 `$UserFieldName / `$PassFieldName"
    exit 1
}

# ---------------- 步骤3: 提取 form action 与隐藏字段 ----------------
$formMatch = [regex]::Match($loginHtml, '<form[^>]*action\s*=\s*["'']([^"'']*)["'']', "IgnoreCase")
if ($formMatch.Success -and $formMatch.Groups[1].Value) {
    $action = $formMatch.Groups[1].Value
} else {
    $action = ""
}
if ($action) {
    $postUrl = [System.Uri]::new([System.Uri]$LoginUrl, $action).AbsoluteUri
} else {
    $postUrl = $LoginUrl
}
Log "登录 POST 地址: $postUrl"

$formData = @{}
foreach ($t in $inputs) {
    $type = Get-InputAttr $t "type"
    if ($type -and $type.ToLower() -eq "hidden") {
        $nm = Get-InputAttr $t "name"
        $vl = Get-InputAttr $t "value"
        if ($nm) { $formData[$nm] = $vl }
    }
}
$formData[$userField] = $Username
$formData[$passField] = $Password

# ---------------- 步骤4: 提交登录 ----------------
Log "提交登录表单..."
try {
    $loginResp2 = Invoke-WebRequest -Uri $postUrl -Method Post -Body $formData `
        -WebSession $webSession -TimeoutSec $TimeoutSec -UseBasicParsing `
        -MaximumRedirection 10
} catch {
    Log "登录请求失败: $_"
    exit 1
}

Log "登录响应状态码: $($loginResp2.StatusCode), 最终URL: $($loginResp2.BaseResponse.ResponseUri)"
Save-Text (Join-Path $OutputDir "debug_login_response.html") $loginResp2.Content

$stillHasLogin = ($loginResp2.Content -match '<input[^>]*type\s*=\s*["'']password["'']', "IgnoreCase")
if ($stillHasLogin) {
    Log "[警告] 登录响应中仍存在密码框, 可能登录失败(密码错误/验证码)"
} else {
    Log "[成功] 未检测到密码框, 疑似登录成功"
}

# ---------------- 步骤5: 抓取考勤页 ----------------
Start-Sleep -Seconds 3
Log "抓取考勤页: $AttendUrl"
try {
    $attResp = Invoke-WebRequest -Uri $AttendUrl -WebSession $webSession -TimeoutSec $TimeoutSec -UseBasicParsing
} catch {
    Log "抓取失败: $_"
    exit 1
}
Log "考勤页状态码: $($attResp.StatusCode)"
$attHtml = $attResp.Content
Save-Text (Join-Path $OutputDir "attendance_page.html") $attHtml

# ---------------- 步骤6: 解析表格并导出 CSV ----------------
$tableMatches = [regex]::Matches($attHtml, '<table[\s\S]*?</table>', "IgnoreCase")
Log "共解析到 $($tableMatches.Count) 张表格"

$idx = 0
foreach ($tbl in $tableMatches) {
    $idx++
    $rows = @()
    $trMatches = [regex]::Matches($tbl.Value, '<tr[\s\S]*?</tr>', "IgnoreCase")
    foreach ($tr in $trMatches) {
        $cells = @()
        $tdMatches = [regex]::Matches($tr.Value, '<t[dh][\s\S]*?</t[dh]>', "IgnoreCase")
        foreach ($td in $tdMatches) {
            $cell = [regex]::Replace($td.Value, '<[^>]+>', '')
            $cell = [System.Net.WebUtility]::HtmlDecode($cell).Trim()
            $cells += $cell
        }
        if ($cells.Count -gt 0) { $rows += ,$cells }
    }
    if ($rows.Count -eq 0) { continue }

    $csvPath = Join-Path $OutputDir ("table_{0}.csv" -f $idx)
    $sb = New-Object System.Text.StringBuilder
    foreach ($r in $rows) {
        $line = ($r | ForEach-Object { '"' + ($_ -replace '"','""') + '"' }) -join ","
        [void]$sb.AppendLine($line)
    }
    [System.IO.File]::WriteAllText($csvPath, $sb.ToString(), [System.Text.Encoding]::UTF8)
    Log "已导出: $csvPath ($($rows.Count) 行)"
}

Log "完成。输出目录: $OutputDir"
