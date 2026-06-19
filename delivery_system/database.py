from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from logger_config import setup_logger
from models import Customer, Order, OrderItem, VALID_STATUSES

logger = setup_logger()


class Database:
    def __init__(self, db_path='data/delivery.db'):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        return connection

    def init_db(self):
        with self.connect() as connection:
            connection.execute('''
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT,
                    address TEXT
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
                    order_date TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('новый','в доставке','выполнен','отменён')),
                    total REAL NOT NULL
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL
                )
            ''')
        logger.info('База данных инициализирована')

    def create_customer(self, name, phone='', address=''):
        customer = Customer(name=name, phone=phone, address=address)
        customer.validate()
        with self.connect() as connection:
            cursor = connection.execute(
                'INSERT INTO customers(name, phone, address) VALUES (?, ?, ?)',
                (customer.name.strip(), customer.phone.strip(), customer.address.strip()),
            )
            customer_id = cursor.lastrowid
        logger.info('Создан клиент id=%s', customer_id)
        return int(customer_id)

    def get_customer(self, customer_id):
        with self.connect() as connection:
            row = connection.execute('SELECT * FROM customers WHERE id = ?', (customer_id,)).fetchone()
        return dict(row) if row else None

    def list_customers(self):
        with self.connect() as connection:
            rows = connection.execute('SELECT * FROM customers ORDER BY id').fetchall()
        return [dict(row) for row in rows]

    def update_customer(self, customer_id, name, phone='', address=''):
        customer = Customer(id=customer_id, name=name, phone=phone, address=address)
        customer.validate()
        with self.connect() as connection:
            cursor = connection.execute(
                'UPDATE customers SET name = ?, phone = ?, address = ? WHERE id = ?',
                (customer.name.strip(), customer.phone.strip(), customer.address.strip(), customer_id),
            )
            if cursor.rowcount == 0:
                raise ValueError('Клиент не найден')
        logger.info('Обновлён клиент id=%s', customer_id)

    def delete_customer(self, customer_id):
        with self.connect() as connection:
            orders_count = connection.execute(
                'SELECT COUNT(*) AS count FROM orders WHERE customer_id = ?',
                (customer_id,),
            ).fetchone()['count']
            if orders_count > 0:
                raise ValueError('Клиента нельзя удалить, потому что у него есть заказы')
            cursor = connection.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
            if cursor.rowcount == 0:
                raise ValueError('Клиент не найден')
        logger.info('Удалён клиент id=%s', customer_id)

    def create_order(self, customer_id, order_date, status, items):
        order_items = self._prepare_items(items)
        order = Order(customer_id=customer_id, order_date=order_date, status=status, items=order_items)
        order.validate()

        if self.get_customer(customer_id) is None:
            raise ValueError('Клиент не найден')

        with self.connect() as connection:
            cursor = connection.execute(
                'INSERT INTO orders(customer_id, order_date, status, total) VALUES (?, ?, ?, ?)',
                (order.customer_id, order.order_date, order.status, order.total),
            )
            order_id = int(cursor.lastrowid)
            for item in order.items:
                connection.execute(
                    'INSERT INTO order_items(order_id, product_name, quantity, price) VALUES (?, ?, ?, ?)',
                    (order_id, item.product_name.strip(), int(item.quantity), float(item.price)),
                )
        logger.info('Создан заказ id=%s', order_id)
        return order_id

    def get_order(self, order_id):
        for order in self.list_orders():
            if order['id'] == order_id:
                return order
        return None

    def list_orders(self, status=None, date_from=None, date_to=None):
        query = '''
            SELECT orders.*, customers.name AS customer_name, customers.phone AS customer_phone,
                   customers.address AS customer_address
            FROM orders
            JOIN customers ON customers.id = orders.customer_id
            WHERE 1 = 1
        '''
        params = []

        if status:
            if status not in VALID_STATUSES:
                raise ValueError('Недопустимый статус заказа')
            query += ' AND orders.status = ?'
            params.append(status)
        if date_from:
            self._validate_date(date_from)
            query += ' AND orders.order_date >= ?'
            params.append(date_from)
        if date_to:
            self._validate_date(date_to)
            query += ' AND orders.order_date <= ?'
            params.append(date_to)

        query += ' ORDER BY orders.order_date DESC, orders.id DESC'

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
            result = []
            for row in rows:
                order = dict(row)
                order['items'] = [dict(item) for item in connection.execute(
                    'SELECT id, product_name, quantity, price FROM order_items WHERE order_id = ? ORDER BY id',
                    (order['id'],),
                ).fetchall()]
                result.append(order)
        return result

    def update_order(self, order_id, customer_id, order_date, status, items):
        order_items = self._prepare_items(items)
        order = Order(id=order_id, customer_id=customer_id, order_date=order_date, status=status, items=order_items)
        order.validate()

        if self.get_customer(customer_id) is None:
            raise ValueError('Клиент не найден')

        with self.connect() as connection:
            cursor = connection.execute(
                'UPDATE orders SET customer_id = ?, order_date = ?, status = ?, total = ? WHERE id = ?',
                (order.customer_id, order.order_date, order.status, order.total, order_id),
            )
            if cursor.rowcount == 0:
                raise ValueError('Заказ не найден')
            connection.execute('DELETE FROM order_items WHERE order_id = ?', (order_id,))
            for item in order.items:
                connection.execute(
                    'INSERT INTO order_items(order_id, product_name, quantity, price) VALUES (?, ?, ?, ?)',
                    (order_id, item.product_name.strip(), int(item.quantity), float(item.price)),
                )
        logger.info('Обновлён заказ id=%s', order_id)

    def delete_order(self, order_id):
        with self.connect() as connection:
            cursor = connection.execute('DELETE FROM orders WHERE id = ?', (order_id,))
            if cursor.rowcount == 0:
                raise ValueError('Заказ не найден')
        logger.info('Удалён заказ id=%s', order_id)

    def count_orders_by_status(self):
        result = {status: 0 for status in VALID_STATUSES}
        with self.connect() as connection:
            rows = connection.execute('SELECT status, COUNT(*) AS count FROM orders GROUP BY status').fetchall()
        for row in rows:
            result[row['status']] = row['count']
        return result

    def top_clients_by_total(self, limit=3):
        with self.connect() as connection:
            rows = connection.execute('''
                SELECT customers.id, customers.name, COALESCE(SUM(orders.total), 0) AS total_sum,
                       COUNT(orders.id) AS orders_count
                FROM customers
                JOIN orders ON orders.customer_id = customers.id
                GROUP BY customers.id, customers.name
                ORDER BY total_sum DESC
                LIMIT ?
            ''', (limit,)).fetchall()
        return [dict(row) for row in rows]

    def revenue_for_period(self, period, reference_date=None):
        start, end = self._period_range(period, reference_date)
        with self.connect() as connection:
            row = connection.execute('''
                SELECT COALESCE(SUM(total), 0) AS revenue
                FROM orders
                WHERE status != 'отменён' AND order_date BETWEEN ? AND ?
            ''', (start, end)).fetchone()
        return round(float(row['revenue']), 2)

    def report(self, period='month', reference_date=None):
        return {
            'period': period,
            'reference_date': reference_date or date.today().isoformat(),
            'orders_by_status': self.count_orders_by_status(),
            'top_clients': self.top_clients_by_total(3),
            'revenue': self.revenue_for_period(period, reference_date),
        }

    def seed_demo_data(self):
        if self.list_customers():
            return
        ivan_id = self.create_customer('Иван Петров', '+7 900 111-22-33', 'Москва, ул. Ленина, 10')
        anna_id = self.create_customer('Анна Смирнова', '+7 900 222-33-44', 'Москва, ул. Мира, 5')
        oleg_id = self.create_customer('Олег Иванов', '+7 900 333-44-55', 'Москва, ул. Садовая, 7')
        today = date.today().isoformat()
        self.create_order(ivan_id, today, 'новый', [
            {'product_name': 'Пицца', 'quantity': 2, 'price': 750},
            {'product_name': 'Сок', 'quantity': 1, 'price': 180},
        ])
        self.create_order(anna_id, today, 'в доставке', [
            {'product_name': 'Суши сет', 'quantity': 1, 'price': 2200},
        ])
        self.create_order(oleg_id, today, 'выполнен', [
            {'product_name': 'Бургер', 'quantity': 3, 'price': 430},
        ])
        logger.info('Добавлены демонстрационные данные')

    def _prepare_items(self, items):
        prepared = []
        for item in items:
            if isinstance(item, OrderItem):
                prepared.append(item)
            else:
                prepared.append(OrderItem(
                    product_name=str(item.get('product_name', '')),
                    quantity=int(item.get('quantity', 0)),
                    price=float(item.get('price', 0)),
                ))
        return prepared

    def _validate_date(self, value):
        try:
            datetime.strptime(value, '%Y-%m-%d')
        except ValueError as exc:
            raise ValueError('Дата должна быть в формате ГГГГ-ММ-ДД') from exc

    def _period_range(self, period, reference_date=None):
        current = date.today()
        if reference_date:
            self._validate_date(reference_date)
            current = datetime.strptime(reference_date, '%Y-%m-%d').date()

        if period == 'day':
            start = current
            end = current
        elif period == 'week':
            start = current - timedelta(days=current.weekday())
            end = start + timedelta(days=6)
        elif period == 'month':
            start = current.replace(day=1)
            if current.month == 12:
                end = current.replace(year=current.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end = current.replace(month=current.month + 1, day=1) - timedelta(days=1)
        else:
            raise ValueError('Период должен быть day, week или month')
        return start.isoformat(), end.isoformat()
