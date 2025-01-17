import unittest
import warnings

from pypika import Case, Query, Tables, Tuple, functions
from pypika.dialects import (
    ClickHouseQuery,
    ClickHouseQueryBuilder,
    MSSQLQuery,
    MSSQLQueryBuilder,
    MySQLLoadQueryBuilder,
    MySQLQuery,
    MySQLQueryBuilder,
    OracleQuery,
    OracleQueryBuilder,
    PostgreSQLQuery,
    PostgreSQLQueryBuilder,
    RedShiftQueryBuilder,
    RedshiftQuery,
    SQLLiteQuery,
    SQLLiteQueryBuilder,
    SnowflakeQuery,
    SnowflakeQueryBuilder,
    VerticaCopyQueryBuilder,
    VerticaCreateQueryBuilder,
    VerticaQuery,
    VerticaQueryBuilder,
)
from pypika.queries import CreateQueryBuilder, DropQueryBuilder, QueryBuilder, ReusedNestedQueryWarning


class QueryTablesTests(unittest.TestCase):
    table_a, table_b, table_c, table_d = Tables("a", "b", "c", "d")

    def test_replace_table(self):
        query = Query.from_(self.table_a).select(self.table_a.time)
        query = query.replace_table(self.table_a, self.table_b)

        self.assertEqual('SELECT "time" FROM "b"', str(query))

    def test_replace_only_specified_table(self):
        query = Query.from_(self.table_a).select(self.table_a.time)
        query = query.replace_table(self.table_b, self.table_c)

        self.assertEqual('SELECT "time" FROM "a"', str(query))

    def test_replace_insert_table(self):
        query = Query.into(self.table_a).insert(1)
        query = query.replace_table(self.table_a, self.table_b)

        self.assertEqual('INSERT INTO "b" VALUES (1)', str(query))

    def test_replace_insert_table_current_table_not_match(self):
        query = Query.into(self.table_a).insert(1)
        query = query.replace_table(self.table_c, self.table_b)

        self.assertEqual('INSERT INTO "a" VALUES (1)', str(query))

    def test_replace_update_table(self):
        query = Query.update(self.table_a).set("foo", "bar")
        query = query.replace_table(self.table_a, self.table_b)

        self.assertEqual('UPDATE "b" SET "foo"=\'bar\'', str(query))

    def test_replace_update_table_current_table_not_match(self):
        query = Query.update(self.table_a).set("foo", "bar")
        query = query.replace_table(self.table_c, self.table_b)

        self.assertEqual('UPDATE "a" SET "foo"=\'bar\'', str(query))

    def test_replace_delete_table(self):
        query = Query.from_(self.table_a).delete()
        query = query.replace_table(self.table_a, self.table_b)

        self.assertEqual('DELETE FROM "b"', str(query))

    def test_replace_join_tables(self):
        query = (
            Query.from_(self.table_a)
            .join(self.table_b)
            .on(self.table_a.customer_id == self.table_b.id)
            .join(self.table_c)
            .on(self.table_b.seller_id == self.table_c.id)
            .select(self.table_a.star)
        )
        query = query.replace_table(self.table_a, self.table_d)

        self.assertEqual(
            'SELECT "d".* '
            'FROM "d" '
            'JOIN "b" ON "d"."customer_id"="b"."id" '
            'JOIN "c" ON "b"."seller_id"="c"."id"',
            str(query),
        )

    def test_replace_filter_tables(self):
        query = Query.from_(self.table_a).select(self.table_a.name).where(self.table_a.name == "Mustermann")
        query = query.replace_table(self.table_a, self.table_b)

        self.assertEqual('SELECT "name" FROM "b" WHERE "name"=\'Mustermann\'', str(query))

    def test_replace_having_table(self):
        query = (
            Query.from_(self.table_a)
            .select(functions.Sum(self.table_a.revenue))
            .groupby(self.table_a.customer)
            .having(functions.Sum(self.table_a.revenue) >= 1000)
        )
        query = query.replace_table(self.table_a, self.table_b)

        self.assertEqual(
            'SELECT SUM("revenue") ' 'FROM "b" ' 'GROUP BY "customer" ' 'HAVING SUM("revenue")>=1000',
            str(query),
        )

    def test_replace_case_table(self):
        query = Query.from_(self.table_a).select(
            Case()
            .when(self.table_a.fname == "Tom", "It was Tom")
            .when(self.table_a.fname == "John", "It was John")
            .else_("It was someone else.")
            .as_("who_was_it")
        )
        query = query.replace_table(self.table_a, self.table_b)

        self.assertEqual(
            "SELECT CASE "
            "WHEN \"fname\"='Tom' THEN 'It was Tom' "
            "WHEN \"fname\"='John' THEN 'It was John' "
            "ELSE 'It was someone else.' END \"who_was_it\" "
            'FROM "b"',
            str(query),
        )

    def test_replace_orderby_table(self):
        query = Query.from_(self.table_a).select(self.table_a.customer).orderby(self.table_a.customer)
        query = query.replace_table(self.table_a, self.table_b)

        self.assertEqual('SELECT "customer" FROM "b" ORDER BY "customer"', str(query))

    def test_replace_tuple_table(self):
        query = (
            Query.from_(self.table_a)
            .select(self.table_a.cost, self.table_a.revenue)
            .where((self.table_a.cost, self.table_a.revenue) == Tuple(1, 2))
        )

        query = query.replace_table(self.table_a, self.table_b)

        # Order is reversed due to lack of right equals method
        self.assertEqual(
            'SELECT "cost","revenue" FROM "b" WHERE (1,2)=("cost","revenue")',
            str(query),
        )

    def test_is_joined(self):
        q = Query.from_(self.table_a).join(self.table_b).on(self.table_a.foo == self.table_b.boo)

        self.assertTrue(q.is_joined(self.table_b))
        self.assertFalse(q.is_joined(self.table_c))

    def test_nested_query_reuse(self):
        sq = Query.from_(self.table_a).select(self.table_a.name, self.table_a.customer)
        self.assertIs(sq.alias, None)
        # A query has already captured sq as a subquery and has changed its alias to sq0
        q1 = Query.from_(sq).select(sq.name)
        self.assertEqual(q1._subquery_count, 1)
        with self.assertWarnsRegex(ReusedNestedQueryWarning, "^Query .* used as a nested subquery elsewhere."):
            q2 = Query.from_(sq).select(sq.customer)
            # This occurs because the inner query is already aliased, so no alias was generated for it and
            # the subquery count used to generate aliases did not increase.
            self.assertEqual(q2._subquery_count, 0)

    def test_joined_query_reuse(self):
        q1 = Query.from_(self.table_a).select(self.table_a.foo, self.table_a.bar)

        q2 = Query.from_(self.table_b).select(self.table_b.bar, self.table_b.boo)
        # When we derive a query from q2, we give it an alias of sq0 here.
        Query.from_(q2).select(q2.bar, q2.boo)

        # When we derive a query from q1, we also give it an alias of sq0 here.
        with self.assertWarnsRegex(ReusedNestedQueryWarning, "^Query .* used as a nested subquery elsewhere."):
            Query.from_(q1).join(q2).on(q1.b == q2.b).select(q1.a, q2.c)
            self.assertEqual(q1.alias, "sq0")
            self.assertEqual(q2.alias, "sq0")


class QueryBuilderTests(unittest.TestCase):
    def test_query_builders_have_reference_to_correct_query_class(self):
        with self.subTest('QueryBuilder'):
            self.assertEqual(Query, QueryBuilder.QUERY_CLS)

        with self.subTest('DropQueryBuilder'):
            self.assertEqual(Query, DropQueryBuilder.QUERY_CLS)

        with self.subTest('CreateQueryBuilder'):
            self.assertEqual(Query, CreateQueryBuilder.QUERY_CLS)

        with self.subTest('MySQLQueryBuilder'):
            self.assertEqual(MySQLQuery, MySQLQueryBuilder.QUERY_CLS)

        with self.subTest('MySQLLoadQueryBuilder'):
            self.assertEqual(MySQLQuery, MySQLLoadQueryBuilder.QUERY_CLS)

        with self.subTest('VerticaQueryBuilder'):
            self.assertEqual(VerticaQuery, VerticaQueryBuilder.QUERY_CLS)

        with self.subTest('VerticaCreateQueryBuilder'):
            self.assertEqual(VerticaQuery, VerticaCreateQueryBuilder.QUERY_CLS)

        with self.subTest('VerticaCopyQueryBuilder'):
            self.assertEqual(VerticaQuery, VerticaCopyQueryBuilder.QUERY_CLS)

        with self.subTest('PostgreSQLQueryBuilder'):
            self.assertEqual(PostgreSQLQuery, PostgreSQLQueryBuilder.QUERY_CLS)

        with self.subTest('MSSQLQueryBuilder'):
            self.assertEqual(MSSQLQuery, MSSQLQueryBuilder.QUERY_CLS)

        with self.subTest('SnowflakeQueryBuilder'):
            self.assertEqual(SnowflakeQuery, SnowflakeQueryBuilder.QUERY_CLS)

        with self.subTest('ClickHouseQueryBuilder'):
            self.assertEqual(ClickHouseQuery, ClickHouseQueryBuilder.QUERY_CLS)

        with self.subTest('RedShiftQueryBuilder'):
            self.assertEqual(RedshiftQuery, RedShiftQueryBuilder.QUERY_CLS)

        with self.subTest('SQLLiteQueryBuilder'):
            self.assertEqual(SQLLiteQuery, SQLLiteQueryBuilder.QUERY_CLS)

        with self.subTest('OracleQueryBuilder'):
            self.assertEqual(OracleQuery, OracleQueryBuilder.QUERY_CLS)
