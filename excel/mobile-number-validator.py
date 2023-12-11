import os, traceback, openpyxl, phonenumbers

# rowsCount - Get last row index (As sheet.max_row is not calculating correctly, doing it manually)
def rowsCount(sheet):
  maxRow = 1

  # Traverse reversely and check if any record is not empty (which is the last record)
  for row in range(sheet.max_row, 0, -1):
    if any(cell.value is not None for cell in sheet[row]):
      maxRow = row
      break

  return maxRow

# rowsCount

# validateMobileNumber
def validateMobileNumber(excelFilePath, mobileNoColumnIndex):
  wb = openpyxl.load_workbook(excelFilePath)
  sheet = wb.active

  rowsCountBeforeDelete = rowsCount(sheet)
  rowsToDelete = []

  # iterate rows
  for row in range(2, rowsCountBeforeDelete + 1):
    mobileNo = sheet.cell(row, mobileNoColumnIndex).value
    isValid = False

    if mobileNo:
      print(f'Validating {mobileNo} at row: {row} ...')

      try:
        res = phonenumbers.parse(mobileNo)

        if res and phonenumbers.is_valid_number(res):
          mobileNoType = phonenumbers.number_type(res)

          # Allow only mobile numbers
          if mobileNoType == phonenumbers.PhoneNumberType.MOBILE or mobileNoType == phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE:
            isValid = True
      except phonenumbers.NumberParseException:
        print(f'Error when parsing {mobileNo}:\n' + traceback.format_exc() + '\n')

        isValid = False

      if not isValid:
        print(f'Invalid: {mobileNo}\n')

        rowsToDelete.append(row)

  if len(rowsToDelete) > 0:
    print('Deleting ' + str(len(rowsToDelete)) + ' invalid records...')

    # Warning: Delete would take some long time
    for rowIndex in rowsToDelete[::-1]:
      sheet.delete_rows(rowIndex)

    rowsCountAfterDelete = rowsCount(sheet)

    print(f'No of records before deletion: {rowsCountBeforeDelete}')
    print(f'No of records deleted: {len(rowsToDelete)}')
    print(f'No of records remaining: {rowsCountAfterDelete}')

    # Check whether deleted correctly
    if (rowsCountAfterDelete + len(rowsToDelete)) == rowsCountBeforeDelete:
      print('Updating the Excel file...')

      wb.save(excelFilePath)
    else:
      print('Total mismatch: [Deleted rows + Remaining records] should be equal to [Records before deletion].')
  else:
    print('All records are file.')

# validateMobileNumber

if __name__ == '__main__':
  excelFilePath = input('Enter the path to Excel file: ')

  if excelFilePath and os.path.isfile(excelFilePath):
    mobileNoColumnIndex = input('Enter the Mobile number column index (starts with 1): ')

    if mobileNoColumnIndex.isnumeric() and int(mobileNoColumnIndex) < 1:
      print('Invalid column index.')
      quit()
    else:
      mobileNoColumnIndex = int(mobileNoColumnIndex)
  else:
    print('Invalid file or the file does not exists.')
    quit()

  validateMobileNumber(excelFilePath, mobileNoColumnIndex)
