import argparse
import requests
import time
import sys
from threading import Thread

def test_host(host, count, results):
    host_results = {
        'Host': host,
        'Success': 0,
        'Failed': 0,
        'Errors': 0,
        'Times': []
    }

    for _ in range(count):
        try:
            start_time = time.time()
            response = requests.get(host, timeout=5)
            elapsed_time = (time.time() - start_time) * 1000
            host_results['Times'].append(elapsed_time)

            if 200 <= response.status_code < 400:
                host_results['Success'] += 1
            else:
                host_results['Failed'] += 1
        except requests.exceptions.RequestException:
            results['Errors'] += 1
    if host_results['Times']:
        host_results['Min'] = min(host_results['Times'])
        host_results['Max'] = max(host_results['Times'])
        host_results['Avg'] = sum(host_results['Times'])/ len(host_results['Times'])
    else:
        host_results['Min'] = 0
        host_results['Max'] = 0
        host_results['Avg'] = 0
    
    results.append(host_results)

def format_result(results, args):
    if not results:
        print("Нет данных для вывода. Все запросы завершились ошибками.", file=sys.stderr)
        return
    
    head = "        Host       | Success | Failed | Errors | Min (ms) | Max (ms) | Avg (ms)"
    separator = "-" * len(head)
    output_lines = [head, separator]
    
    for res in results:
        if '://' in res['Host']:
            host_clean = res['Host'].split('://', 1)[1]
        else:
            host_clean = res['Host']

        line = (f"{host_clean:<18} | {res['Success']:^7} | {res['Failed']:^6} |")
        line += (f" {res['Errors']:^6} | {res['Min']:>8.2f} | {res['Max']:>8.2f} | {res['Avg']:>8.2f}")
        output_lines.append(line)

    output_text = "\n".join(output_lines)

    
    if args.output:
        try:
            with open(args.output, 'w') as f:
                f.write(output_text)
            print(f"Результаты сохранены в файл: {args.output}")
        except IOError as e:
            print(f"Ошибка записи в файл: {str(e)}", file=sys.stderr)
    else:
        print(output_text)

def validate_args(args):
    if args.count <= 0:
        print("Ошибка: кол-во запросов должно быть положительным числом", file=sys.stderr)
        return False

    if args.hosts and not args.hosts.strip():
        print("Ошибка: список хостов не может быть пустым", file=sys.stderr)
        return False

    if args.file:
        try:
            with open(args.file, 'r') as f:
                if not f.read().strip():
                    print("Ошибка: файл с хостами пуст", file=sys.stderr)
                    return False
        except IOError as e:
            print(f"Ошибка чтения файла: {str(e)}", file=sys.stderr)
            return False

    return True
        
def main():
    parser = argparse.ArgumentParser(description="Программа для тестирования серверов")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-H', '--hosts', help="Список хостов через запятую без пробелов")
    group.add_argument('-F', '--file', help="Имя файла с хостами (каждый хост с новой строки)")
    parser.add_argument('-O', '--output', help="Имя выходного файла")
    parser.add_argument('-C', '--count', type=int, default=1, help="Количество тестовых запросов (по умолчанию: 1)")

    try:
        args = parser.parse_args()

        if not validate_args(args):
            sys.exit(1)

        if args.hosts:    
            hosts = args.hosts.split(",")
        else:
            try:
                with open(args.file, 'r') as f:
                    hosts = [line.strip() for line in f.readlines() if line.strip()]
            except IOError as e:
                print(f"Ошибка чтения файла: {str(e)}", file=sys.stderr)
                sys.exit(1)
        if not hosts:
            print("Ошибка: не указаны хосты для тестирования", file=sys.stderr)
            sys.exit(1)

        results = []
        threads = []

        print(f"Начинаем тестирование хостов({len(hosts)} шт.) по заданному кол-ву запроов ({args.count} шт.)")
        
        for host in hosts:
            thread = Thread(target=test_host, args=(host, args.count, results))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        format_result(results, args)

    except argparse.ArgumentError as e:
        print(f"Ошибка в переданных аргументах: {str(e)}", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {str(e)}", file=sys.stderr)
        sys.exit(1)

        
if __name__ == "__main__":
    main()
