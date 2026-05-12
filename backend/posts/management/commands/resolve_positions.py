from django.core.management.base import BaseCommand
from posts.position_resolution import resolve_positions

class Command(BaseCommand):
    help = 'Runs the automated position resolution engine to update PENDING and ACTIVE positions'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting position resolution...'))
        try:
            resolve_positions()
            self.stdout.write(self.style.SUCCESS('Position resolution completed successfully.'))
            
            from posts.profitability import recalculate_all_profitabilities
            self.stdout.write(self.style.SUCCESS('Recalculating profitabilities...'))
            recalculate_all_profitabilities()
            self.stdout.write(self.style.SUCCESS('Profitabilities updated successfully.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error during position resolution: {e}'))
