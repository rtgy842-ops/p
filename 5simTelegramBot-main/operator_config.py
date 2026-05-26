import sqlite3
import logging
from data.service_countries import get_all_service_countries

class OperatorConfig:
    def __init__(self):
        self.setup_database()
        
    def setup_database(self):
        try:
            conn = sqlite3.connect('admin.db')
            cursor = conn.cursor()
            
            # ایجاد جدول تنظیمات اپراتور با ساختار جدید
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS operator_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT NOT NULL,
                    country TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    country_name TEXT NOT NULL,
                    UNIQUE(service, country)
                )
            ''')
            
            # تنظیمات از المصدر الموحد (Single Source of Truth)
            default_settings = get_all_service_countries()
            
            # اضافه کردن تنظیمات جدید
            cursor.executemany('''
                INSERT OR REPLACE INTO operator_settings (service, country, operator, country_name)
                VALUES (?, ?, ?, ?)
            ''', default_settings)
            
            conn.commit()
            conn.close()
            logging.info("Operator settings database updated successfully")
            
        except Exception as e:
            logging.error(f"Error in setup_database: {e}")
            
    def get_operator_info(self, service, country):
        try:
            conn = sqlite3.connect('admin.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT operator, country_name FROM operator_settings 
                WHERE service = ? AND country = ?
            ''', (service, country))
            result = cursor.fetchone()
            conn.close()
            return result if result else (None, None)
        except Exception as e:
            logging.error(f"Error in get_operator_info: {e}")
            return None, None
            
    def set_operator(self, service, country, operator, country_name):
        try:
            conn = sqlite3.connect('admin.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO operator_settings (service, country, operator, country_name)
                VALUES (?, ?, ?, ?)
            ''', (service, country, operator, country_name))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logging.error(f"Error in set_operator: {e}")
            return False
            
    def get_all_settings(self):
        try:
            conn = sqlite3.connect('admin.db')
            cursor = conn.cursor()
            cursor.execute('SELECT service, country, operator, country_name FROM operator_settings')
            settings = cursor.fetchall()
            conn.close()
            return settings
        except Exception as e:
            logging.error(f"Error in get_all_settings: {e}")
            return [] 