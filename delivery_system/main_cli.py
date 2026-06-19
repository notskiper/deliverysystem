from __future__ import annotations

import argparse
import json

from data_export import export_orders, import_orders
from database import Database
from logger_config import setup_logger
from models import VALID_STATUSES

logger = setup_logger()


def parse_items(items_text):
    result = []
    for raw_item in items_text.split(';'):
        raw_item = raw_item.strip()
        if not raw_item:
            continue
        parts = raw_item.split(':')
        if len(parts) != 3:
            raise ValueError('Товары вводятся в формате Название:Количество:Цена;Название:Количество:Цена')
        result.append({
            'product_name': parts[0].strip(),
            'quantity': int(parts[1]),
            'price': float(parts[2].replace(',', '.')),
        })
    if not result:
        raise ValueError('Нужно указать хотя бы один товар')
    return result


def print_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=4))


def handle_report(args, db):
    print_json(db.report(args.period, args.date))


def handle_export(args, db):
    count = export_orders(db, args.file)
    print(f'Экспорт завершён. Заказов экспортировано: {count}. Файл: {args.file}')


def handle_import(args, db):
    count = import_orders(db, args.file)
    print(f'Импорт завершён. Заказов импортировано: {count}. Файл: {args.file}')


def handle_seed(args, db):
    db.seed_demo_data()
    print('Демонстрационные данные добавлены. Если данные уже были, повторно они не добавлялись.')


def handle_customer(args, db):
    if args.action == 'add':
        customer_id = db.create_customer(args.name, args.phone, args.address)
        print(f'Клиент создан. ID: {customer_id}')
    elif args.action == 'list':
        print_json(db.list_customers())
    elif args.action == 'update':
        db.update_customer(args.id, args.name, args.phone, args.address)
        print('Клиент обновлён.')
    elif args.action == 'delete':
        db.delete_customer(args.id)
        print('Клиент удалён.')


def handle_order(args, db):
    if args.action == 'add':
        order_id = db.create_order(args.customer_id, args.date, args.status, parse_items(args.items))
        print(f'Заказ создан. ID: {order_id}')
    elif args.action == 'list':
        print_json(db.list_orders(args.status, args.date_from, args.date_to))
    elif args.action == 'update':
        db.update_order(args.id, args.customer_id, args.date, args.status, parse_items(args.items))
        print('Заказ обновлён.')
    elif args.action == 'delete':
        db.delete_order(args.id)
        print('Заказ удалён.')


def build_parser():
    parser = argparse.ArgumentParser(description='Внутренняя система учёта заказов компании «Быстрая доставка»')
    parser.add_argument('--db', default='data/delivery.db', help='Путь к SQLite-файлу базы данных')
    subparsers = parser.add_subparsers(dest='command')

    report_parser = subparsers.add_parser('report', help='Показать отчёт')
    report_parser.add_argument('--period', choices=['day', 'week', 'month'], default='month')
    report_parser.add_argument('--date', help='Дата для расчёта периода в формате ГГГГ-ММ-ДД')
    report_parser.set_defaults(func=handle_report)

    export_parser = subparsers.add_parser('export', help='Экспортировать заказы в JSON или XML')
    export_parser.add_argument('--file', required=True, help='Файл .json или .xml')
    export_parser.set_defaults(func=handle_export)

    import_parser = subparsers.add_parser('import', help='Импортировать заказы из JSON или XML')
    import_parser.add_argument('--file', required=True, help='Файл .json или .xml')
    import_parser.set_defaults(func=handle_import)

    seed_parser = subparsers.add_parser('seed', help='Добавить демонстрационные данные')
    seed_parser.set_defaults(func=handle_seed)

    customer_parser = subparsers.add_parser('customer', help='CRUD для клиентов')
    customer_subparsers = customer_parser.add_subparsers(dest='action')

    customer_add = customer_subparsers.add_parser('add')
    customer_add.add_argument('--name', required=True)
    customer_add.add_argument('--phone', default='')
    customer_add.add_argument('--address', default='')
    customer_add.set_defaults(func=handle_customer)

    customer_list = customer_subparsers.add_parser('list')
    customer_list.set_defaults(func=handle_customer)

    customer_update = customer_subparsers.add_parser('update')
    customer_update.add_argument('--id', type=int, required=True)
    customer_update.add_argument('--name', required=True)
    customer_update.add_argument('--phone', default='')
    customer_update.add_argument('--address', default='')
    customer_update.set_defaults(func=handle_customer)

    customer_delete = customer_subparsers.add_parser('delete')
    customer_delete.add_argument('--id', type=int, required=True)
    customer_delete.set_defaults(func=handle_customer)

    order_parser = subparsers.add_parser('order', help='CRUD для заказов')
    order_subparsers = order_parser.add_subparsers(dest='action')

    order_add = order_subparsers.add_parser('add')
    order_add.add_argument('--customer-id', type=int, required=True)
    order_add.add_argument('--date', required=True)
    order_add.add_argument('--status', choices=VALID_STATUSES, required=True)
    order_add.add_argument('--items', required=True, help='Например: "Пицца:2:750;Сок:1:180"')
    order_add.set_defaults(func=handle_order)

    order_list = order_subparsers.add_parser('list')
    order_list.add_argument('--status', choices=VALID_STATUSES)
    order_list.add_argument('--date-from')
    order_list.add_argument('--date-to')
    order_list.set_defaults(func=handle_order)

    order_update = order_subparsers.add_parser('update')
    order_update.add_argument('--id', type=int, required=True)
    order_update.add_argument('--customer-id', type=int, required=True)
    order_update.add_argument('--date', required=True)
    order_update.add_argument('--status', choices=VALID_STATUSES, required=True)
    order_update.add_argument('--items', required=True)
    order_update.set_defaults(func=handle_order)

    order_delete = order_subparsers.add_parser('delete')
    order_delete.add_argument('--id', type=int, required=True)
    order_delete.set_defaults(func=handle_order)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, 'func'):
        parser.print_help()
        return
    db = Database(args.db)
    try:
        args.func(args, db)
    except Exception as exc:
        logger.exception('Ошибка выполнения CLI-команды')
        print(f'Ошибка: {exc}')
        return


if __name__ == '__main__':
    main()
