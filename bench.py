#!/usr/bin/env python3
"""
bench.py — консольная утилита для проверки доступности HTTP(S)-серверов
и замера времени ответа.

Пример запуска:
    python bench.py -H https://ya.ru,https://google.com -C 5

Полное описание — см. readme.md
"""

import argparse
import asyncio
import re
import sys
import time
from dataclasses import dataclass, field

try:
    import httpx
except ImportError:
    print(
        "Ошибка: не найдена библиотека 'httpx'. "
        "Установите зависимости командой: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)


# Регулярное выражение для проверки формата адреса вида https://example.com
URL_PATTERN = re.compile(
    r"^https?://"                      # схема http:// или https://
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?"   # домен / хост
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)*"  # поддомены
    r"(?::\d+)?"                       # необязательный порт
    r"(?:/[^\s]*)?$"                   # необязательный путь
)

REQUEST_TIMEOUT = 10.0  # секунд, максимальное время ожидания ответа


@dataclass
class HostStats:
    host: str
    success: int = 0
    failed: int = 0
    errors: int = 0
    times: list = field(default_factory=list)

    def add_success(self, elapsed: float):
        self.success += 1
        self.times.append(elapsed)

    def add_failed(self, elapsed: float):
        self.failed += 1
        self.times.append(elapsed)

    def add_error(self):
        self.errors += 1

    @property
    def min_time(self):
        return min(self.times) if self.times else None

    @property
    def max_time(self):
        return max(self.times) if self.times else None

    @property
    def avg_time(self):
        return sum(self.times) / len(self.times) if self.times else None


def positive_int(value: str) -> int:
    """Проверяет, что переданное значение — целое положительное число."""
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"'{value}' не является числом. Параметр --count должен быть целым числом."
        )
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(
            f"'{value}' некорректно. Параметр --count должен быть положительным числом."
        )
    return ivalue


def validate_host(host: str) -> str:
    """Проверяет, что адрес соответствует формату https://example.com."""
    host = host.strip()
    if not URL_PATTERN.match(host):
        raise ValueError(
            f"Некорректный формат адреса: '{host}'. "
            f"Ожидается формат вида https://example.com"
        )
    return host


def parse_args():
    parser = argparse.ArgumentParser(
        prog="bench.py",
        description="Консольная программа для тестирования доступности серверов по HTTP.",
    )

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "-H", "--hosts",
        type=str,
        help="Список хостов через запятую без пробелов, например: "
             "https://ya.ru,https://google.com",
    )
    source_group.add_argument(
        "-F", "--file",
        type=str,
        help="Путь до файла со списком адресов, по одному на строку.",
    )

    parser.add_argument(
        "-C", "--count",
        type=positive_int,
        default=1,
        help="Количество запросов на каждый хост (по умолчанию 1).",
    )

    parser.add_argument(
        "-O", "--output",
        type=str,
        default=None,
        help="Путь до файла для сохранения результата. "
             "Если не указан — вывод в консоль.",
    )

    return parser.parse_args()


def load_hosts(args) -> list:
    """Считывает и валидирует список хостов из аргументов -H или -F."""
    raw_hosts = []

    if args.hosts:
        raw_hosts = args.hosts.split(",")
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                raw_hosts = [line for line in f.read().splitlines() if line.strip()]
        except FileNotFoundError:
            raise ValueError(f"Файл не найден: '{args.file}'")
        except OSError as e:
            raise ValueError(f"Не удалось прочитать файл '{args.file}': {e}")

    if not raw_hosts:
        raise ValueError("Список хостов пуст. Укажите хотя бы один адрес.")

    validated = []
    for h in raw_hosts:
        h = h.strip()
        if not h:
            continue
        validated.append(validate_host(h))

    return validated


async def make_request(client: httpx.AsyncClient, host: str, stats: HostStats):
    """Выполняет один HTTP-запрос и обновляет статистику."""
    start = time.perf_counter()
    try:
        response = await client.get(host, timeout=REQUEST_TIMEOUT)
        elapsed = time.perf_counter() - start

        if response.status_code >= 400:
            stats.add_failed(elapsed)
        else:
            stats.add_success(elapsed)

    except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
        # Сервер недоступен, таймаут, ошибка DNS и т.п.
        stats.add_error()
    except Exception:
        # Любая непредвиденная ошибка тоже считается "Errors",
        # чтобы программа не падала целиком.
        stats.add_error()


async def bench_host(host: str, count: int) -> HostStats:
    """Выполняет count запросов к одному хосту (конкурентно) и возвращает статистику."""
    stats = HostStats(host=host)
    async with httpx.AsyncClient() as client:
        tasks = [make_request(client, host, stats) for _ in range(count)]
        await asyncio.gather(*tasks)
    return stats


async def run_benchmark(hosts: list, count: int) -> list:
    """Запускает тестирование всех хостов конкурентно."""
    tasks = [bench_host(host, count) for host in hosts]
    return await asyncio.gather(*tasks)


def format_time(value):
    return f"{value:.4f} с" if value is not None else "н/д"


def format_results(results: list) -> str:
    """Формирует человекочитаемый отчёт по результатам тестирования."""
    lines = []
    separator = "=" * 50
    for stats in results:
        lines.append(separator)
        lines.append(f"Host:    {stats.host}")
        lines.append(f"Success: {stats.success}")
        lines.append(f"Failed:  {stats.failed}")
        lines.append(f"Errors:  {stats.errors}")
        lines.append(f"Min:     {format_time(stats.min_time)}")
        lines.append(f"Max:     {format_time(stats.max_time)}")
        lines.append(f"Avg:     {format_time(stats.avg_time)}")
    lines.append(separator)
    return "\n".join(lines)


def main():
    args = parse_args()

    try:
        hosts = load_hosts(args)
    except ValueError as e:
        print(f"Ошибка входных данных: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        results = asyncio.run(run_benchmark(hosts, args.count))
    except Exception as e:
        print(f"Непредвиденная ошибка при выполнении запросов: {e}", file=sys.stderr)
        sys.exit(1)

    report = format_results(results)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(report + "\n")
            print(f"Результат сохранён в файл: {args.output}")
        except OSError as e:
            print(f"Не удалось записать в файл '{args.output}': {e}", file=sys.stderr)
            print(report)
    else:
        print(report)


if __name__ == "__main__":
    main()
