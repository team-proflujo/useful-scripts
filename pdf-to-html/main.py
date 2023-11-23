import os, mammoth, traceback, bs4
from typing import Final
from pdf2docx import Converter

OUTPUT_DIR: Final = 'outputs'

# convertPDFIntoDocx
def convertPDFIntoDocx(pdfFile):
    docxFile = os.path.join(OUTPUT_DIR, ''.join(os.path.basename(pdfFile).split('.')[:-1])) + '.docx'

    cv = Converter(pdfFile)

    cv.convert(docxFile)

    cv.close()

    return docxFile

# convertPDFIntoDocx

# convertDocxIntoHTML
def convertDocxIntoHTML(docxFile):
    htmlFile = os.path.join(OUTPUT_DIR, ''.join(os.path.basename(docxFile).split('.')[:-1])) + '.html'
    htmlContent = None

    with open(docxFile, 'rb') as fpDocx:
        htmlContent = mammoth.convert_to_html(fpDocx)

    if htmlContent:
        with open(htmlFile, 'w', encoding = 'utf-8') as fpHTML:
            fpHTML.write(htmlContent.value)

    os.remove(docxFile)

# convertDocxIntoHTML

# main
def main():
    try:
        folderPath = input('Enter the folder which contains the PDF files to be converted: ')

        if folderPath and os.path.isdir(folderPath):
            if not os.path.isdir(OUTPUT_DIR):
                os.makedirs(OUTPUT_DIR)

            for file in os.listdir(folderPath):
                filePath = os.path.join(folderPath, file)

                if os.path.isfile(filePath) and filePath.endswith('.pdf'):
                    docxFile = os.path.join(OUTPUT_DIR, ''.join(os.path.basename(filePath).split('.')[:-1])) + '.docx'
                    htmlFilePath = os.path.join(OUTPUT_DIR, ''.join(os.path.basename(filePath).split('.')[:-1])) + '.html'

                    if os.path.isfile(htmlFilePath):
                        print(f'{htmlFilePath} already converted.')
                    else:
                        if os.path.isfile(docxFile):
                            print(os.path.basename(docxFile) + ' already exists.')
                        else:
                            docxFile = convertPDFIntoDocx(filePath)

                        convertDocxIntoHTML(docxFile)

            print(f'Success. All the PDF files at {folderPath} have been converted into HTML file. Please find the HTML files at: {OUTPUT_DIR}')
        else:
            print('Invalid path or the Folder does not exists.')
    except:
        print('Error occurred: ' + traceback.format_exc())

# main

if __name__ == '__main__':
    main()
