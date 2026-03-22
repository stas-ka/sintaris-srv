$HtmlFolder = "happytram_full_site"
$htmlFiles = Get-ChildItem -Path $HtmlFolder -Recurse -Include *.html -File

if ($htmlFiles.Count -eq 0) {
    Write-Host "NO files here $HtmlFolder"
    return
}

foreach ($file in $htmlFiles) {
    $content = Get-Content $file.FullName -Raw

    # Принудительно сохраняем как UTF-8 без BOM
    [System.IO.File]::WriteAllText($file.FullName, $content, [System.Text.Encoding]::UTF8)
    Write-Host "Without BOM: $($file.FullName)"
}

Write-Host "done"
