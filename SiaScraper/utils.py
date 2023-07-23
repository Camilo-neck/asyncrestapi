from flask import Response
import json
import os

def padTo2Digits(num):
  return str(num).zfill(2)

def formatDate(date):
  return (
    '-'.join([
      str(date.year),
      padTo2Digits(date.month),
      padTo2Digits(date.day)
    ]) + ' ' + ':'.join([
      padTo2Digits(date.hour),
      padTo2Digits(date.minute)
    ])
  )

def filter_list(lista, txt):
	return [element for element in lista if txt not in [*element.values()][0]]

def saveJSON(obj,name,folderPath):
  if not os.path.exists(folderPath): os.mkdir(folderPath)
  with open(f'{folderPath}/{name}.json', 'w', encoding='utf-8') as fp: json.dump(obj, fp , ensure_ascii=False)
