$HtmlFolder = "happytram_full_site"

Get-ChildItem -Path $HtmlFolder -Recurse -Filter *.html | ForEach-Object {
    $file = $_.FullName
    $content = Get-Content $file -Raw

    # Check if <meta charset="utf-8"> is present
    if ($content -notmatch '<meta\s+charset\s*=\s*["' + "'" + ']utf-8["' + "'" + ']') {
        $insertMeta = '<meta charset="utf-8">'
        $content = $content -replace '<head>', '<head>' + "`n" + $insertMeta
        Write-Host ("Added meta charset in: " + $file)
    }

    # Save in UTF-8 without BOM
    [System.IO.File]::WriteAllText($file, $content, [System.Text.Encoding]::UTF8)
    Write-Host ("Saved as UTF-8 (no BOM): " + $file)
}

Write-Host "HTML done"
