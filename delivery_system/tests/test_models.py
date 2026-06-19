import pytest

from models import Customer, Order, OrderItem


def test_customer_name_required():
    customer = Customer(name='')
    with pytest.raises(ValueError):
        customer.validate()


def test_order_total_is_calculated():
    order = Order(customer_id=1, order_date='2026-06-19', status='новый', items=[
        OrderItem('Пицца', 2, 500),
        OrderItem('Сок', 3, 100),
    ])
    order.validate()
    assert order.total == 1300


def test_order_invalid_status():
    order = Order(customer_id=1, order_date='2026-06-19', status='ошибка', items=[OrderItem('Пицца', 1, 500)])
    with pytest.raises(ValueError):
        order.validate()
