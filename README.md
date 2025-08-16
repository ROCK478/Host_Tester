# Host_Tester
## Программа для тестирования серверов

Инструкция по запуску:
1. Проверьте, установлен ли Python: python --version (Если нет, установите)
2. Проверьте, установлен ли pip: pip --version (Если нет, установите)
3. Перейдите в папку с репозиторием
4. Введите в консоль: pip install -r requirements.txt
5. Запускаем программу:
   
  python HostTester.py [-h] (-H HOSTS | -F FILE) [-O OUTPUT] [-C COUNT]
  
  -h - Вывод help
   
  -H - Перечисление хостов без пробелов через запятую, например:  https://ya.ru,https://google.com
  
  -F - Имя файла для чтения хостов (хосты должны быть с новой строчки). Как пример создан файл test.txt
  
  -O - Имя выходного файла для сохранения результатов
  
  -С - Количество запросов к каждому хосту (по умолчанию: 1)

Примеры запуска:

python HostTester.py -F test.txt

python HostTester.py -H https://ya.ru,https://google.com -C 5

python HostTester.py -h

python HostTester.py -F test.txt -O output.txt
