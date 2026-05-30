# Task 10: Reorganize Backend Tests

## Objective
Currently, all test files for the `posts` app (e.g., `test_resolution.py`, `test_position_resolution.py`, `test_views.py`) are placed adjacently in the `backend/posts/` directory. As the test suite grows, this clutters the app directory.

## Implementation Steps
1. Create a `tests/` subdirectory inside `backend/posts/`.
2. Move all `test_*.py` files into the new `tests/` directory.
3. Ensure that `__init__.py` is present in the `tests/` directory so Django's test runner can discover them properly.
4. Update any relative imports within the test files if necessary.
5. Run `uv run python manage.py test posts` to verify that all tests are still discovered and execute successfully.
