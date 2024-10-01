#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from dataclasses import dataclass
import json
import pathlib
import sys
import random
from typing import List

OUTPUT_DIR = "/home/kardymon-d/ydb3/ydb/ydb/library/yql/tools/dqrun/data"
QUERIES_NUM = 1
TABLE_NAME = "pq.`match`"
ROW_NUM = 550000
UINT64_COLUMN_NUM = 20
STR32_COLUMN_NUM = 10
STR64_COLUMN_NUM = 10
COLUMN_NUM = UINT64_COLUMN_NUM + STR32_COLUMN_NUM + STR64_COLUMN_NUM
FILLED_COLUMN_NUM = 40
Row = List



# OUTPUT_DIR = "/home/kardymon-d/ydb3/ydb/ydb/library/yql/tools/dqrun/data"
# QUERIES_NUM = 1
# TABLE_NAME = "pq.`match`"
# ROW_NUM = 600000
# UINT64_COLUMN_NUM = 3
# STR32_COLUMN_NUM = 1
# STR64_COLUMN_NUM = 1
# COLUMN_NUM = UINT64_COLUMN_NUM + STR32_COLUMN_NUM + STR64_COLUMN_NUM
# FILLED_COLUMN_NUM = 5
# Row = List


def get_timer() -> int:
    get_timer.timer += 1
    return get_timer.timer
get_timer.timer = 0


@dataclass
class Table:
    name: str
    column_names: List[str]
    column_types: List[str]
    rows: List[Row]


def validate() -> None:
    assert(QUERIES_NUM < ROW_NUM)
    assert(0 < FILLED_COLUMN_NUM <= COLUMN_NUM)


def gen_column_names(column_num: int) -> List[str]:
    return [f"c{i}" for i in range(column_num)]


def gen_column_types(column_num: int) -> List[str]:
    column_types = ["uint64" if i < UINT64_COLUMN_NUM else "str32" if i < UINT64_COLUMN_NUM + STR32_COLUMN_NUM else "str64" for i in range(column_num)]
    random.shuffle(column_types)
    return column_types


def type_to_sql(column_type: str) -> str:
    if column_type == "uint64":
        return "Uint64"
    elif column_type == "str32":
        return "String"
    elif column_type == "str64":
        return "String"
    else:
        raise RuntimeError()


def int_to_str(n: int, length: int) -> str:
    result = ""
    while n > 0:
        div, mod = divmod(n, 26)
        result += chr(ord('a') + mod)
        n = div
    result += 'a' * (length - len(result))
    return result


def gen_cell(row_index: int, column_type: str):
    value = 2 * row_index
    if column_type == "uint64":
        return value
    elif column_type == "str32":
        return int_to_str(value, 32)
    elif column_type == "str64":
        return int_to_str(value, 100)
    else:
        raise RuntimeError()


def gen_row(row_index: int, column_types: List[str]) -> Row:
    are_filled = [i < FILLED_COLUMN_NUM for i in range(len(column_types))]
    random.shuffle(are_filled)
    return [gen_cell(row_index, column_type) if is_filled else None for is_filled, column_type in zip(are_filled, column_types)]


def gen_table(name: str, column_names: List[str], column_types: List[str], rows: List[Row]) -> Table:
    return Table(
        name,
        [*column_names, "time"],
        [*column_types, "uint64"],
        [[*row, get_timer()] for row in rows],
    )


def write_table(filename: str, table: Table) -> None:
    with open(filename, "w") as file:
        for row in table.rows:
            json_doc = dict(zip(table.column_names, row))
            json.dump({key: value for key, value in json_doc.items() if value is not None}, file)
            file.write('\n')


def gen_value(query_index: int, table: Table) -> str:
    index = query_index % len(table.column_types)
    column_type = table.column_types[index]
    
    l = len(table.rows)
    print(f"ffff {l}")
    value = table.rows[l - 2][index]
    print(f"    value {value} type {column_type}")
    #return value
    
    #value = query_index % (2 * ROW_NUM)
    if column_type == "uint64":
        return f"{value}UL"
    elif column_type == "str32":
        return f'"{value}"'
    elif column_type == "str64":
        return f'"{value}"'
    else:
        raise RuntimeError()


def gen_query(query_index: int, table: Table, value: str) -> str:
    return f"""
    PRAGMA dq.MaxTasksPerStage="1";
$match = SELECT *
FROM {table.name}
WITH (
    FORMAT=json_each_row,
    SCHEMA
    (
        {",".join([name + " " + type_to_sql(type) for name, type in zip(table.column_names, table.column_types)])}
    )
)
WHERE {table.column_names[query_index % len(table.column_names)]} == {value};

INSERT INTO pq.`match2`
SELECT ToBytes(Unwrap(Yson::SerializeJson(Yson::From(TableRow())))) FROM $match;
"""


def write_query(filename: str, query: str) -> None:
    with open(filename, "w") as file:
        file.write(query)


def parse_args():
    parser = argparse.ArgumentParser(
        description="",
        epilog='Example: ./gen',
    )
    parser.add_argument('-p', '--pipe-only', dest='pipe_only', default=False, action='store_true')
    args = parser.parse_args()
    return args

def gen_only_to_cout(column_names, column_types):
    row_index = 0

    while True:
        row = gen_row(row_index, column_types)
        #print(f"rows {row}")

        json_doc = dict(zip(column_names, row))
        json.dump({key: value for key, value in json_doc.items() if value is not None}, sys.stdout)
        sys.stdout.write('\n')
    
        row_index = row_index + 1



def main():
    args = parse_args()
    validate()
   # print(f"p  {args.pipe_only}")

    column_names = gen_column_names(COLUMN_NUM)
    column_types = gen_column_types(COLUMN_NUM)

    if args.pipe_only:
        gen_only_to_cout(column_names, column_types)
        return
    rows = [gen_row(row_index, column_types) for row_index in range(ROW_NUM)]
    
    table = gen_table(TABLE_NAME, column_names, column_types, rows)
    write_table(f"{OUTPUT_DIR}/data.txt", table)

    pathlib.Path(f"{OUTPUT_DIR}/query/").mkdir(parents=True, exist_ok=True)
    for query_index in range(QUERIES_NUM):
        value = gen_value(query_index, table)
        write_query(f"{OUTPUT_DIR}/query/{query_index}.txt", gen_query(query_index, table, value))


if __name__ == "__main__":
    main()
