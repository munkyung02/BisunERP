param([string]$ProjectRoot = (Get-Location).Path)
$ErrorActionPreference = "Stop"
Write-Host "BisunERP v3.2 통합 패치 적용" -ForegroundColor Cyan
$required=@("main.py","app","modules","data")
foreach($item in $required){$target=Join-Path $ProjectRoot $item;if(-not(Test-Path $target)){throw "ERP 루트가 아닙니다: $target"}}
$patchRoot=Split-Path -Parent $MyInvocation.MyCommand.Path
$backupRoot=Join-Path $ProjectRoot ("backup\\full_patch_"+(Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Force -Path $backupRoot|Out-Null
$files=@("app\\main_window.py","modules\\settings\\settings_service.py","modules\\settings\\settings_page.py","modules\\shipments\\shipment_repository.py","modules\\shipments\\shipment_service.py","modules\\shipments\\shipment_page.py","modules\\shipments\\simple_import_dialog.py")
foreach($relative in $files){$current=Join-Path $ProjectRoot $relative;if(Test-Path $current){$backupFile=Join-Path $backupRoot $relative;New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupFile)|Out-Null;Copy-Item $current $backupFile -Force}}
Copy-Item (Join-Path $patchRoot "app\\*") (Join-Path $ProjectRoot "app") -Recurse -Force
Copy-Item (Join-Path $patchRoot "modules\\*") (Join-Path $ProjectRoot "modules") -Recurse -Force
Write-Host "백업: $backupRoot" -ForegroundColor DarkGray
Push-Location $ProjectRoot
try{
$compile=@("modules\\mappings\\dictionary.py","modules\\mappings\\scorer.py","modules\\mappings\\mapping_engine.py","modules\\coupang\\coupang_api.py","modules\\coupang\\coupang_order_service.py","modules\\coupang\\coupang_scheduler.py","modules\\coupang\\coupang_shipment_service.py","modules\\shipments\\shipment_repository.py","modules\\shipments\\shipment_service.py","modules\\shipments\\shipment_page.py","modules\\shipments\\simple_import_dialog.py","app\\main_window.py")
foreach($relative in $compile){Write-Host "검사: $relative";python -m py_compile $relative;if($LASTEXITCODE -ne 0){throw "문법검사 실패: $relative"}}
Write-Host "통합 패치 적용 완료" -ForegroundColor Green
Write-Host "다음 명령: python main.py" -ForegroundColor Yellow
}finally{Pop-Location}
