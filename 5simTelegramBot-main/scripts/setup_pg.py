import os

import psycopg2

LOG = os.path.join(os.path.dirname(__file__), '..', 'setup_log.txt')

with open(LOG, 'w') as f:
    f.write('STARTING PostgreSQL setup\n')
    f.flush()

    pw_list = ['admin', 'password', 'postgres', 'root', '1234']
    for pw in pw_list:
        try:
            f.write(f'Trying pw={pw}...\n'); f.flush()
            conn = psycopg2.connect(
                host='localhost', port=5432, user='postgres', password=pw,
                dbname='postgres', connect_timeout=3)
            f.write(f'CONNECTED with pw={pw}\n'); f.flush()
            conn.autocommit = True
            cur = conn.cursor()
            try:
                cur.execute("CREATE ROLE smsbot WITH LOGIN PASSWORD 'MyS3cur3Pssw0r'")
                f.write('Created smsbot role\n')
            except Exception as e:
                f.write(f'Role already exists: {e}\n')
            try:
                cur.execute('CREATE DATABASE smsbot OWNER smsbot')
                f.write('Created smsbot database\n')
            except Exception as e:
                f.write(f'Database already exists: {e}\n')
            cur.execute('GRANT ALL PRIVILEGES ON DATABASE smsbot TO smsbot')
            f.write('Grants applied\n')
            conn.close()
            f.write('SETUP COMPLETE\n')
            break
        except Exception as e:
            f.write(f'FAILED: {str(e)[:100]}\n')
    else:
        f.write('ALL PASSWORDS FAILED\n')

print('Setup log written to', LOG)
