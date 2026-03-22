'''
Created on 23.08.2024

@author: sulme
'''
import trafilatura
import sys
from trafilatura.baseline import html2txt

import PyPDF2
import fitz
import pytesseract
from PIL import Image
import io
import os

def recognize_text_from_image(image_bytes):
    try:
        #image = Image.frombytes("RGB", (image_bytes.shape[1], image_bytes.shape[0]), image_bytes)
        image = Image.open(io.BytesIO(image_bytes))
        #image.save('mein_bild_neu.png', format='PNG')
        #extracted_text = pytesseract.image_to_string(image, lang='rus', config='--psm 6 --oem 3')
        extracted_text = pytesseract.image_to_string(image, lang='deu', config='--psm 6 --oem 3')
        #print(f"Erkannter Text:\n{extracted_text}")
        return extracted_text
    except Exception as e:
        print(f"Fehler bei der Texterkennung: {e}")


def extractTextFromPdf(pdfFilePath:str, outputFilePath:str):
    # Open the PDF file (replace 'your_pdf.pdf' with your actual PDF file)
    
    # Create a PDF reader object
    
    # Initialize an empty string to store the extracted text
    extracted_text = ""
    
    # Save the extracted text to a TXT file (replace 'output.txt' with your desired file name)
    #, encoding='utf-8'


    with open(outputFilePath, 'w', encoding='utf-8') as txt_file:
        #pdf_reader = PyPDF2.PdfReader(pdf_file)
        #pdf_file = open(pdfFilePath, 'rb')
        pdf_reader = fitz.open(pdfFilePath)  # PDF-Datei öffnen
        for page_num in range(pdf_reader.page_count):
        # Iterate through each page in the PDF
        #for page_num in range(len(pdf_reader.pages)):
            #page = pdf_reader.pages[page_num]
            #extracted_text = page.extract_text()
            page = pdf_reader[page_num]
            extracted_text = page.get_text("text")  # Text von der Seite extrahieren
                #extracted_text = page.get_text()
            save_to_file(txt_file, extracted_text)
            images = page.get_images(full=True)  # Bilder auf der Seite extrahieren
            for img_index, img in enumerate(images, start=1):
                #extracted_text = img.get_text("text")  # Text aus dem Bild extrahieren
                xref = img[0]
                base_image = pdf_reader.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                extracted_text = recognize_text_from_image(image_bytes)
                #extracted_text = pytesseract.image_to_string(img)

                #print(f"Extrahierter Text:\n{extracted_text}")
                #print(f"Seite {page_num + 1}, Bild {img_index + 1}:\n{extracted_text}\n{'-' * 50}")
                save_to_file(txt_file, extracted_text)
        
    # Close the PDF file
    #pdf_file.close()
    
    
    print(f"Text extracted and saved to {outputFilePath}")
    
import glob

#def convert_alle_pdf_dateien(startDir:str, outputPostfix:str):
 #   pattern=startDir+'./**/*.pdf'
  #  pdf_dateien = glob.glob(pattern, recursive=True)
  #  for pdf_pfad in pdf_dateien:
  #      # Hier kannst du den PDF-Pfad weiterverarbeiten (z. B. einlesen)
   #     extractTextFromPdf(pdf_pfad, pdf_pfad+outputPostfix)
def convert_alle_pdf_dateien(startDir:str, outputFolder:str):
    pattern = os.path.join(startDir, '**', '*.pdf')
    pdf_dateien = glob.glob(pattern, recursive=True)
    
    os.makedirs(outputFolder, exist_ok=True)  # Falls noch nicht vorhanden

    for pdf_pfad in pdf_dateien:
        pdf_name = os.path.splitext(os.path.basename(pdf_pfad))[0] + '.txt'
        output_path = os.path.join(outputFolder, pdf_name)
        extractTextFromPdf(pdf_pfad, output_path)


def download_page_content(url):
    try:
        html_content = trafilatura.fetch_url(url)
        return html_content
    except Exception as e:
        print(f"Ошибка при загрузке {url}: {e}")
        return None

#def save_to_file(file, content:str):
 #   file.write(content + '\n')
def save_to_file(file, content: str):
    if content is None:
        content = ""
    file.write(content + '\n')
        
def extractTextFromWebSite(file_path:str, output_file:str):
    try:
        with open(file_path, 'r') as file:
            
            urls = file.readlines()
            with open(output_file, 'a', encoding='utf-8') as output:
                for url in urls:
                    url = url.strip()  # Убираем лишние пробелы и переносы строк
                    print(f"Обработка адреса: {url}")
                    content = download_page_content(url)
                    if content:
                        # Извлекаем основной текст и заголовок
                        headers = trafilatura.extract(content)
                        save_to_file(output, f"{url}")
                        save_to_file(output, "{")
                        metadata = trafilatura.extract_metadata(content)
                        save_to_file(output, f"Заголовок: {metadata.title, 'Нет заголовка'}")
                        save_to_file(output, f"Описание: {metadata.description, 'Нет описания'}")
                        save_to_file(output, "Содержание:")
                        save_to_file(output, html2txt(content))
                        save_to_file(output, "}\n")
                        #save_to_file(output_file, "-" * 50)
                        print(f"Содержание сохранено с {url}")
                    else:
                        print(f"Не удалось загрузить содержание с {url}")
    except FileNotFoundError:
        print(f"Файл {file_path} не найден.")

def main():
    if len(sys.argv) != 4:
        print("Использование: <command> <путь к input файлу.txt> <путь к extract файлу.txt>")
        return
    
    # команда
    command = sys.argv[1]
    # Путь к вашему текстовому файлу с адресами страниц
    file_path = sys.argv[2]
    #file_path = 'sitemap.txt'
    output_file = sys.argv[3]
    #output_file = 'content_with_headers.txt'

    if command == 'extract_web':
        extractTextFromWebSite(file_path, output_file)
    elif command == 'extract_pdf':
        if os.path.isdir(file_path):
            convert_alle_pdf_dateien(file_path, output_file)
        elif file_path.lower().endswith('.pdf'):
            extractTextFromPdf(file_path, output_file)
    else:
        print(f"Unknown <command> {command}")
        

if __name__ == "__main__":
    main()

