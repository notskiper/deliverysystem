from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

VALID_STATUSES = ('новый', 'в доставке', 'выполнен', 'отменён')


@dataclass
class Customer:
    name: str
    phone: str = ''
    address: str = ''
    id: int = None

    def validate(self):
        if not self.name or not self.name.strip():
            raise ValueError('Имя клиента не может быть пустым')


@dataclass
class OrderItem:
    product_name: str
    quantity: int
    price: float
    id: int = None

    def validate(self):
        if not self.product_name or not self.product_name.strip():
            raise ValueError('Название товара не может быть пустым')
        if int(self.quantity) <= 0:
            raise ValueError('Количество товара должно быть больше 0')
        if float(self.price) < 0:
            raise ValueError('Цена товара не может быть отрицательной')

    @property
    def total(self):
        return round(int(self.quantity) * float(self.price), 2)


@dataclass
class Order:
    customer_id: int
    order_date: str
    status: str
    items: list = field(default_factory=list)
    id: int = None
    total: float = 0.0

    def validate(self):
        if not self.customer_id:
            raise ValueError('Не выбран клиент')
        try:
            datetime.strptime(self.order_date, '%Y-%m-%d')
        except ValueError as exc:
            raise ValueError('Дата заказа должна быть в формате ГГГГ-ММ-ДД') from exc
        if self.status not in VALID_STATUSES:
            raise ValueError('Недопустимый статус заказа')
        if not self.items:
            raise ValueError('В заказе должен быть хотя бы один товар')
        for item in self.items:
            item.validate()
        self.total = round(sum(item.total for item in self.items), 2)
