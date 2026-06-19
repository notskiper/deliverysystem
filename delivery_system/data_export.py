from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from database import Database
from logger_config import setup_logger
from models import VALID_STATUSES

logger = setup_logger()


def export_orders(db, file_path):
    path = Path(file_path)
    if path.parent != Path('.'):
        path.parent.mkdir(parents=True, exist_ok=True)
    orders = db.list_orders()

    if path.suffix.lower() == '.json':
        _export_json(orders, path)
    elif path.suffix.lower() == '.xml':
        _export_xml(orders, path)
    else:
        raise ValueError('Поддерживаются только файлы .json и .xml')

    logger.info('Экспортировано заказов: %s в файл %s', len(orders), path)
    return len(orders)


def import_orders(db, file_path):
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError('Файл импорта не найден')

    if path.suffix.lower() == '.json':
        orders = _import_json(path)
    elif path.suffix.lower() == '.xml':
        orders = _import_xml(path)
    else:
        raise ValueError('Поддерживаются только файлы .json и .xml')

    imported_count = 0
    for order in orders:
        customer_id = _resolve_customer(db, order)
        db.create_order(
            customer_id=customer_id,
            order_date=order['order_date'],
            status=order['status'],
            items=order['items'],
        )
        imported_count += 1

    logger.info('Импортировано заказов: %s из файла %s', imported_count, path)
    return imported_count


def _export_json(orders, path):
    path.write_text(json.dumps({'orders': orders}, ensure_ascii=False, indent=4), encoding='utf-8')


def _export_xml(orders, path):
    root = ET.Element('orders')
    for order in orders:
        order_node = ET.SubElement(root, 'order')
        _add_text(order_node, 'id', order['id'])
        _add_text(order_node, 'customer_id', order['customer_id'])
        _add_text(order_node, 'customer_name', order.get('customer_name', ''))
        _add_text(order_node, 'customer_phone', order.get('customer_phone', ''))
        _add_text(order_node, 'customer_address', order.get('customer_address', ''))
        _add_text(order_node, 'order_date', order['order_date'])
        _add_text(order_node, 'status', order['status'])
        _add_text(order_node, 'total', order['total'])

        items_node = ET.SubElement(order_node, 'items')
        for item in order['items']:
            item_node = ET.SubElement(items_node, 'item')
            _add_text(item_node, 'product_name', item['product_name'])
            _add_text(item_node, 'quantity', item['quantity'])
            _add_text(item_node, 'price', item['price'])

    _indent_xml(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding='utf-8', xml_declaration=True)


def _import_json(path):
    try:
        raw_data = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError('Некорректный JSON-файл') from exc

    orders = raw_data.get('orders') if isinstance(raw_data, dict) else raw_data
    if not isinstance(orders, list):
        raise ValueError('JSON должен содержать список заказов или объект с ключом orders')
    return [_normalize_order(order) for order in orders]


def _import_xml(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError('Некорректный XML-файл') from exc

    if root.tag != 'orders':
        raise ValueError('Корневой тег XML должен быть orders')

    orders = []
    for order_node in root.findall('order'):
        items = []
        items_node = order_node.find('items')
        if items_node is not None:
            for item_node in items_node.findall('item'):
                items.append({
                    'product_name': _node_text(item_node, 'product_name'),
                    'quantity': int(float(_node_text(item_node, 'quantity', '0'))),
                    'price': float(_node_text(item_node, 'price', '0')),
                })

        orders.append(_normalize_order({
            'customer_id': _optional_int(_node_text(order_node, 'customer_id', '')),
            'customer_name': _node_text(order_node, 'customer_name', ''),
            'customer_phone': _node_text(order_node, 'customer_phone', ''),
            'customer_address': _node_text(order_node, 'customer_address', ''),
            'order_date': _node_text(order_node, 'order_date'),
            'status': _node_text(order_node, 'status'),
            'items': items,
        }))
    return orders


def _normalize_order(order):
    if not isinstance(order, dict):
        raise ValueError('Каждый заказ должен быть объектом')

    customer_data = order.get('customer') if isinstance(order.get('customer'), dict) else {}
    customer_id = order.get('customer_id')
    customer_name = order.get('customer_name') or customer_data.get('name', '')
    customer_phone = order.get('customer_phone') or customer_data.get('phone', '')
    customer_address = order.get('customer_address') or customer_data.get('address', '')

    if customer_id is not None:
        try:
            customer_id = int(customer_id)
        except (TypeError, ValueError) as exc:
            raise ValueError('customer_id должен быть числом') from exc

    order_date = str(order.get('order_date', '')).strip()
    status = str(order.get('status', '')).strip()
    items = order.get('items', [])

    if status not in VALID_STATUSES:
        raise ValueError('Недопустимый статус в файле импорта')
    if not order_date:
        raise ValueError('В заказе отсутствует дата')
    if not isinstance(items, list) or not items:
        raise ValueError('В заказе должен быть список товаров')

    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Каждый товар должен быть объектом')
        normalized_items.append({
            'product_name': str(item.get('product_name', '')).strip(),
            'quantity': int(item.get('quantity', 0)),
            'price': float(item.get('price', 0)),
        })

    return {
        'customer_id': customer_id,
        'customer_name': str(customer_name or '').strip(),
        'customer_phone': str(customer_phone or '').strip(),
        'customer_address': str(customer_address or '').strip(),
        'order_date': order_date,
        'status': status,
        'items': normalized_items,
    }


def _resolve_customer(db, order):
    customer_id = order.get('customer_id')
    if customer_id and db.get_customer(customer_id):
        return int(customer_id)

    customer_name = order.get('customer_name')
    if not customer_name:
        raise ValueError('Для импорта нужен существующий customer_id или customer_name')

    for customer in db.list_customers():
        if customer['name'].lower() == customer_name.lower():
            return int(customer['id'])

    return db.create_customer(customer_name, order.get('customer_phone', ''), order.get('customer_address', ''))


def _add_text(parent, tag, value):
    node = ET.SubElement(parent, tag)
    node.text = str(value)


def _node_text(parent, tag, default=None):
    node = parent.find(tag)
    if node is None or node.text is None:
        if default is None:
            raise ValueError('В XML отсутствует обязательное поле ' + tag)
        return default
    return node.text


def _optional_int(value):
    if value == '':
        return None
    return int(float(value))


def _indent_xml(element, level=0):
    indent = '\n' + level * '    '
    child_indent = '\n' + (level + 1) * '    '
    children = list(element)
    if children:
        if not element.text or not element.text.strip():
            element.text = child_indent
        for child in children:
            _indent_xml(child, level + 1)
        if not children[-1].tail or not children[-1].tail.strip():
            children[-1].tail = indent
    if level and (not element.tail or not element.tail.strip()):
        element.tail = indent
