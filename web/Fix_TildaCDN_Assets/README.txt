
📄 Инструкция

1. Распакуйте содержимое архива.
2. Поместите папку "happytram_full_pages" рядом с этим скриптом (если её ещё нет).
3. Откройте PowerShell и выполните:

   Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
   .\Fix-AllTildaAssets.ps1

4. Скрипт скачает все изображения и стили с TildaCDN и заменит их в HTML, CSS, JS.
