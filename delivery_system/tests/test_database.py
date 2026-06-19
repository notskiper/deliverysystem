import pytest

from database import Database


@pytest.fixture()
def db(tmp_path):
    return Database(str(tmp_path / 'test_delivery.db'))


def test_customer_crud(db):
    customer_id = db.create_customer('Иван', '+7', 'Москва')
    assert db.get_customer(customer_id)['name'] == 'Иван'
    db.update_customer(customer_id, 'Иван Петров', '+7 111', 'Саратов')
    assert db.get_customer(customer_id)['address'] == 'Саратов'
    db.delete_customer(customer_id)
    assert db.get_customer(customer_id) is None


def test_customer_cannot_be_deleted_with_orders(db):
    customer_id = db.create_customer('Анна')
    db.create_order(customer_id, '2026-06-19', 'новый', [{'product_name': 'Пицца', 'quantity': 2, 'price': 700}])
    with pytest.raises(ValueError):
        db.delete_customer(customer_id)


def test_order_crud_and_filter(db):
    customer_id = db.create_customer('Олег')
    order_id = db.create_order(customer_id, '2026-06-19', 'новый', [{'product_name': 'Бургер', 'quantity': 3, 'price': 300}])
    assert db.get_order(order_id)['total'] == 900
    db.update_order(order_id, customer_id, '2026-06-20', 'выполнен', [{'product_name': 'Суши', 'quantity': 1, 'price': 1200}])
    filtered = db.list_orders(status='выполнен', date_from='2026-06-01', date_to='2026-06-30')
    assert len(filtered) == 1
    assert filtered[0]['total'] == 1200
    db.delete_order(order_id)
    assert db.get_order(order_id) is None


def test_report(db):
    first = db.create_customer('Первый')
    second = db.create_customer('Второй')
    db.create_order(first, '2026-06-19', 'выполнен', [{'product_name': 'Пицца', 'quantity': 2, 'price': 1000}])
    db.create_order(second, '2026-06-19', 'отменён', [{'product_name': 'Сок', 'quantity': 1, 'price': 300}])
    report = db.report('month', '2026-06-19')
    assert report['orders_by_status']['выполнен'] == 1
    assert report['orders_by_status']['отменён'] == 1
    assert report['revenue'] == 2000
    assert report['top_clients'][0]['name'] == 'Первый'
