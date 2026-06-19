from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from data_export import export_orders, import_orders
from database import Database
from models import VALID_STATUSES


class DeliveryApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Быстрая доставка - учёт заказов')
        self.root.geometry('980x620')
        self.db = Database()
        self.status_filter = tk.StringVar(value='все')
        self.date_from_filter = tk.StringVar()
        self.date_to_filter = tk.StringVar()
        self.export_format = tk.StringVar(value='json')
        self.build_widgets()
        self.db.seed_demo_data()
        self.refresh_orders()

    def build_widgets(self):
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill='x')

        ttk.Label(top_frame, text='Статус:').pack(side='left')
        ttk.Combobox(top_frame, textvariable=self.status_filter, values=('все',) + VALID_STATUSES, state='readonly', width=16).pack(side='left', padx=5)
        ttk.Label(top_frame, text='Дата от:').pack(side='left', padx=(15, 0))
        ttk.Entry(top_frame, textvariable=self.date_from_filter, width=12).pack(side='left', padx=5)
        ttk.Label(top_frame, text='Дата до:').pack(side='left', padx=(15, 0))
        ttk.Entry(top_frame, textvariable=self.date_to_filter, width=12).pack(side='left', padx=5)
        ttk.Button(top_frame, text='Применить фильтр', command=self.refresh_orders).pack(side='left', padx=10)
        ttk.Button(top_frame, text='Сбросить', command=self.clear_filters).pack(side='left')

        columns = ('id', 'date', 'customer', 'status', 'total')
        self.tree = ttk.Treeview(self.root, columns=columns, show='headings', height=18)
        headings = {'id': 'ID', 'date': 'Дата', 'customer': 'Клиент', 'status': 'Статус', 'total': 'Сумма'}
        widths = {'id': 60, 'date': 120, 'customer': 280, 'status': 150, 'total': 120}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column])
        self.tree.pack(fill='both', expand=True, padx=10, pady=5)

        buttons_frame = ttk.Frame(self.root, padding=10)
        buttons_frame.pack(fill='x')
        ttk.Button(buttons_frame, text='Добавить', command=self.add_order).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text='Редактировать', command=self.edit_order).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text='Удалить', command=self.delete_order).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text='Клиенты', command=self.show_customers_window).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text='Показать отчёт', command=self.show_report).pack(side='left', padx=20)
        ttk.Label(buttons_frame, text='Формат:').pack(side='left')
        ttk.Combobox(buttons_frame, textvariable=self.export_format, values=('json', 'xml'), state='readonly', width=8).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text='Экспорт', command=self.export_file).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text='Импорт', command=self.import_file).pack(side='left', padx=5)

    def refresh_orders(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        status = None if self.status_filter.get() == 'все' else self.status_filter.get()
        date_from = self.date_from_filter.get().strip() or None
        date_to = self.date_to_filter.get().strip() or None
        try:
            orders = self.db.list_orders(status=status, date_from=date_from, date_to=date_to)
        except Exception as exc:
            messagebox.showerror('Ошибка фильтра', str(exc))
            return
        for order in orders:
            self.tree.insert('', 'end', values=(order['id'], order['order_date'], order['customer_name'], order['status'], f"{order['total']:.2f}"))

    def clear_filters(self):
        self.status_filter.set('все')
        self.date_from_filter.set('')
        self.date_to_filter.set('')
        self.refresh_orders()

    def selected_order_id(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning('Выбор заказа', 'Выберите заказ в таблице')
            return None
        return int(self.tree.item(selection[0], 'values')[0])

    def add_order(self):
        OrderForm(self.root, self.db, on_save=self.refresh_orders)

    def edit_order(self):
        order_id = self.selected_order_id()
        if order_id:
            OrderForm(self.root, self.db, order_id=order_id, on_save=self.refresh_orders)

    def delete_order(self):
        order_id = self.selected_order_id()
        if order_id and messagebox.askyesno('Удаление', 'Удалить выбранный заказ?'):
            try:
                self.db.delete_order(order_id)
                self.refresh_orders()
            except Exception as exc:
                messagebox.showerror('Ошибка удаления', str(exc))

    def show_report(self):
        report = self.db.report('month')
        window = tk.Toplevel(self.root)
        window.title('Отчёт за месяц')
        window.geometry('520x420')
        text = tk.Text(window, wrap='word', padx=10, pady=10)
        text.pack(fill='both', expand=True)
        text.insert('end', 'Количество заказов по статусам:\n')
        for status, count in report['orders_by_status'].items():
            text.insert('end', f'{status}: {count}\n')
        text.insert('end', '\nТоп-3 клиента по сумме заказов:\n')
        for client in report['top_clients']:
            text.insert('end', f"{client['name']} - {client['total_sum']:.2f} руб., заказов: {client['orders_count']}\n")
        text.insert('end', f"\nОбщая выручка за месяц: {report['revenue']:.2f} руб.\n")
        text.config(state='disabled')

    def show_customers_window(self):
        CustomerWindow(self.root, self.db)

    def export_file(self):
        file_name = 'orders_backup.' + self.export_format.get()
        try:
            count = export_orders(self.db, file_name)
            messagebox.showinfo('Экспорт', f'Экспортировано заказов: {count}\nФайл: {file_name}')
        except Exception as exc:
            messagebox.showerror('Ошибка экспорта', str(exc))

    def import_file(self):
        file_name = 'orders_backup.' + self.export_format.get()
        try:
            count = import_orders(self.db, file_name)
            self.refresh_orders()
            messagebox.showinfo('Импорт', f'Импортировано заказов: {count}\nФайл: {file_name}')
        except Exception as exc:
            messagebox.showerror('Ошибка импорта', str(exc))


class OrderForm:
    def __init__(self, parent, db, order_id=None, on_save=None):
        self.db = db
        self.order_id = order_id
        self.on_save = on_save
        self.order = db.get_order(order_id) if order_id else None
        self.window = tk.Toplevel(parent)
        self.window.title('Редактирование заказа' if order_id else 'Добавление заказа')
        self.window.geometry('620x520')
        self.customer_var = tk.StringVar()
        self.date_var = tk.StringVar()
        self.status_var = tk.StringVar(value='новый')
        self.build_form()
        self.fill_form()

    def build_form(self):
        frame = ttk.Frame(self.window, padding=15)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Клиент:').grid(row=0, column=0, sticky='w', pady=5)
        self.customers = self.db.list_customers()
        values = [f"{customer['id']} - {customer['name']}" for customer in self.customers]
        self.customer_box = ttk.Combobox(frame, textvariable=self.customer_var, values=values, state='readonly', width=45)
        self.customer_box.grid(row=0, column=1, sticky='we', pady=5)
        ttk.Label(frame, text='Дата заказа:').grid(row=1, column=0, sticky='w', pady=5)
        ttk.Entry(frame, textvariable=self.date_var, width=20).grid(row=1, column=1, sticky='w', pady=5)
        ttk.Label(frame, text='Статус:').grid(row=2, column=0, sticky='w', pady=5)
        ttk.Combobox(frame, textvariable=self.status_var, values=VALID_STATUSES, state='readonly', width=20).grid(row=2, column=1, sticky='w', pady=5)
        ttk.Label(frame, text='Товары: один товар на строку в формате Название;Количество;Цена').grid(row=3, column=0, columnspan=2, sticky='w', pady=(15, 5))
        self.items_text = tk.Text(frame, height=12, width=60)
        self.items_text.grid(row=4, column=0, columnspan=2, sticky='nsew')
        ttk.Button(frame, text='Сохранить', command=self.save).grid(row=5, column=0, columnspan=2, pady=15)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

    def fill_form(self):
        if self.order:
            for value in self.customer_box['values']:
                if value.startswith(f"{self.order['customer_id']} - "):
                    self.customer_var.set(value)
                    break
            self.date_var.set(self.order['order_date'])
            self.status_var.set(self.order['status'])
            self.items_text.insert('1.0', '\n'.join([f"{item['product_name']};{item['quantity']};{item['price']}" for item in self.order['items']]))
        elif self.customer_box['values']:
            self.customer_box.current(0)

    def save(self):
        try:
            if not self.customer_var.get():
                raise ValueError('Сначала добавьте клиента')
            customer_id = int(self.customer_var.get().split(' - ')[0])
            items = self.parse_items()
            if self.order_id:
                self.db.update_order(self.order_id, customer_id, self.date_var.get().strip(), self.status_var.get(), items)
            else:
                self.db.create_order(customer_id, self.date_var.get().strip(), self.status_var.get(), items)
            if self.on_save:
                self.on_save()
            self.window.destroy()
        except Exception as exc:
            messagebox.showerror('Ошибка сохранения', str(exc))

    def parse_items(self):
        result = []
        for line in self.items_text.get('1.0', 'end').splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(';')
            if len(parts) != 3:
                raise ValueError('Каждая строка товара должна иметь формат: Название;Количество;Цена')
            result.append({'product_name': parts[0].strip(), 'quantity': int(parts[1]), 'price': float(parts[2].replace(',', '.'))})
        if not result:
            raise ValueError('Добавьте хотя бы один товар')
        return result


class CustomerWindow:
    def __init__(self, parent, db):
        self.db = db
        self.window = tk.Toplevel(parent)
        self.window.title('Клиенты')
        self.window.geometry('760x430')
        columns = ('id', 'name', 'phone', 'address')
        self.tree = ttk.Treeview(self.window, columns=columns, show='headings', height=12)
        for column, text in zip(columns, ('ID', 'Имя', 'Телефон', 'Адрес')):
            self.tree.heading(column, text=text)
        self.tree.pack(fill='both', expand=True, padx=10, pady=10)
        form = ttk.Frame(self.window, padding=10)
        form.pack(fill='x')
        self.name_var = tk.StringVar()
        self.phone_var = tk.StringVar()
        self.address_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=20).pack(side='left', padx=5)
        ttk.Entry(form, textvariable=self.phone_var, width=18).pack(side='left', padx=5)
        ttk.Entry(form, textvariable=self.address_var, width=30).pack(side='left', padx=5)
        ttk.Button(form, text='Добавить', command=self.add_customer).pack(side='left', padx=5)
        ttk.Button(form, text='Удалить выбранного', command=self.delete_customer).pack(side='left', padx=5)
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for customer in self.db.list_customers():
            self.tree.insert('', 'end', values=(customer['id'], customer['name'], customer['phone'], customer['address']))

    def add_customer(self):
        try:
            self.db.create_customer(self.name_var.get(), self.phone_var.get(), self.address_var.get())
            self.name_var.set('')
            self.phone_var.set('')
            self.address_var.set('')
            self.refresh()
        except Exception as exc:
            messagebox.showerror('Ошибка', str(exc))

    def delete_customer(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning('Выбор клиента', 'Выберите клиента')
            return
        customer_id = int(self.tree.item(selection[0], 'values')[0])
        try:
            self.db.delete_customer(customer_id)
            self.refresh()
        except Exception as exc:
            messagebox.showerror('Ошибка удаления', str(exc))


def main():
    root = tk.Tk()
    DeliveryApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
