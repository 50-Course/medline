#!/bin/bash

# generate migrations
alembic revision --autogenerate -m 'Initial Migration'
# apply the migration
alembic upgrade head
