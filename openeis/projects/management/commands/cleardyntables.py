'''This command iterates through all tables in the database. All tables
which name starts with appoutputdata_ and are empty are dropped.
'''

from optparse import make_option

from django.core.management.base import NoArgsCommand
from django.db import connection, transaction


class Command(NoArgsCommand):
    help = 'Remove orphaned dynamic application output tables.'
    option_list = NoArgsCommand.option_list + (
        make_option('-n', '--dry-run', action='store_true', default=False,
                    help='Do everything except modify the database.'),
        make_option('-a', '--all-tables', action='store_true', default=False,
                    help='Also drop non-empty dynamic tables.'),
    )

    def handle_noargs(self, *, verbosity=1, dry_run=False, all_tables=False,
                      **options):
        verbosity = int(verbosity)
        with transaction.atomic():
            cursor = connection.cursor()
            for table in cursor.db.introspection.get_table_list(cursor):
                if not table.startswith('appoutputdata_'):
                    continue
                if not all_tables:
                    cursor.execute('SELECT COUNT(*) FROM ' + table)
                    count, = cursor.curser.fetchone()
                    if count:
                        continue
                if verbosity >= 2:
                    self.stdout.write('Dropping table: {}'.format(table))
                if not dry_run:
                    cursor.execute('DROP TABLE ' + table)