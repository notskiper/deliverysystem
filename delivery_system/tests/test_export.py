import json
import pytest

from data_export import export_orders, import_orders
from database import Database


@pytest.fixture()
def filled_db(tmp_path):
    db = Database(str(tmp_path / 'filled.db'))
    customer_id = db.create_customer('Иван', '+7 900', 'Москва')
    db.create_order(customer_id, '2026-06-19', 'новый', [
        {'product_name': 'Пицца', 'quantity': 2, 'price': 750},
        {'product_name': 'Сок', 'quantity': 1, 'price': 150},
    ])
    return db


def test_export_json(filled_db, tmp_path):
    file_path = tmp_path / 'orders.json'
    count = export_orders(filled_db, str(file_path))
    data = json.loads(file_path.read_text(encoding='utf-8'))
    assert count == 1
    assert data['orders'][0]['customer_name'] == 'Иван'
    assert data['orders'][0]['total'] == 1650


def test_import_json(tmp_path):
    db = Database(str(tmp_path / 'import_json.db'))
    file_path = tmp_path / 'orders.json'
    file_path.write_text(json.dumps({'orders': [{
        'customer_name': 'Мария',
        'customer_phone': '+7 111',
        'customer_address': 'Казань',
        'order_date': '2026-06-19',
        'status': 'новый',
        'items': [{'product_name': 'Роллы', 'quantity': 1, 'price': 900}],
    }]}, ensure_ascii=False), encoding='utf-8')
    assert import_orders(db, str(file_path)) == 1
    assert db.list_customers()[0]['name'] == 'Мария'
    assert db.list_orders()[0]['total'] == 900


def test_export_and_import_xml(filled_db, tmp_path):
    export_file = tmp_path / 'orders.xml'
    new_db = Database(str(tmp_path / 'import_xml.db'))
    export_orders(filled_db, str(export_file))
    assert import_orders(new_db, str(export_file)) == 1
    assert new_db.list_customers()[0]['name'] == 'Иван'
    assert new_db.list_orders()[0]['total'] == 1650


def test_import_invalid_format(filled_db, tmp_path):
    file_path = tmp_path / 'orders.txt'
    file_path.write_text('bad', encoding='utf-8')
    with pytest.raises(ValueError):
        import_orders(filled_db, str(file_path))
