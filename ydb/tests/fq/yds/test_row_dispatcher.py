#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pytest
import logging

from ydb.tests.tools.fq_runner.kikimr_utils import yq_v1
from ydb.tests.tools.datastreams_helpers.test_yds_base import TestYdsBase

from ydb.tests.tools.datastreams_helpers.control_plane import list_read_rules
from ydb.tests.tools.datastreams_helpers.control_plane import create_stream, create_read_rule
from ydb.tests.tools.datastreams_helpers.data_plane import read_stream

import ydb.public.api.protos.draft.fq_pb2 as fq

YDS_CONNECTION = "yds"


def start_yds_query(kikimr, client, sql) -> str:
    query_id = client.create_query("simple", sql, type=fq.QueryContent.QueryType.STREAMING).result.query_id
    client.wait_query_status(query_id, fq.QueryMeta.RUNNING)
    kikimr.compute_plane.wait_zero_checkpoint(query_id)
    return query_id


def stop_yds_query(client, query_id):
    client.abort_query(query_id)
    client.wait_query(query_id)


class TestPqReadWrite(TestYdsBase):

    @yq_v1
    @pytest.mark.parametrize("mvp_external_ydb_endpoint", [{"endpoint": os.getenv("YDB_ENDPOINT")}], indirect=True)
    def test_row_dispatcher_simple(self, kikimr, client):
        client.create_yds_connection(name=YDS_CONNECTION, database_id="FakeDatabaseId")
        self.init_topics(Rf"pq_test_pq_read_write", create_output = False)
        
        output_topic1 = "pq_test_pq_read_write_output1"
        output_topic2 = "pq_test_pq_read_write_output2"
        output_topic3 = "pq_test_pq_read_write_output3"
        create_stream(output_topic1, partitions_count=1)
        create_read_rule(output_topic1, self.consumer_name)

        create_stream(output_topic2, partitions_count=1)
        create_read_rule(output_topic2, self.consumer_name)

        create_stream(output_topic3, partitions_count=1)
        create_read_rule(output_topic3, self.consumer_name)

        sql1 = Rf'''
            INSERT INTO {YDS_CONNECTION}.`{output_topic1}`
            SELECT * FROM {YDS_CONNECTION}.`{self.input_topic}`;'''
        sql2 = Rf'''
            INSERT INTO {YDS_CONNECTION}.`{output_topic2}`
            SELECT * FROM {YDS_CONNECTION}.`{self.input_topic}`;'''
        query_id1 = start_yds_query(kikimr, client, sql1)
        query_id2 = start_yds_query(kikimr, client, sql2)

        data = [
            '{"time" = 101;}',
            '{"time" = 102;}'
        ]

        self.write_stream(data)
        expected = data
        assert self.read_stream(len(expected), topic_path = output_topic1) == expected
        assert self.read_stream(len(expected), topic_path = output_topic2) == expected

        assert kikimr.control_plane.get_actor_count(1, "DQ_PQ_READ_ACTOR") == 2
        assert kikimr.control_plane.get_actor_count(1, "YQ_ROW_DISPATCHER_SESSION") == 1

        # nothing unnecessary...
        assert not read_stream(output_topic1, 1, True, self.consumer_name, timeout = 1)
        assert not read_stream(output_topic2, 1, True, self.consumer_name, timeout = 1)

        sql3 = Rf'''
            INSERT INTO {YDS_CONNECTION}.`{output_topic3}`
            SELECT * FROM {YDS_CONNECTION}.`{self.input_topic}`;'''
        query_id3 = start_yds_query(kikimr, client, sql3)

        data = ['{"time" = 103;}']
        self.write_stream(data)
        expected = data

        assert self.read_stream(len(expected), topic_path = output_topic1) == expected
        assert self.read_stream(len(expected), topic_path = output_topic2) == expected
        assert self.read_stream(len(expected), topic_path = output_topic3) == expected

        stop_yds_query(client, query_id1)
        stop_yds_query(client, query_id2)
        stop_yds_query(client, query_id3)

        # Assert that all read rules were removed after query stops
        read_rules = list_read_rules(self.input_topic)
        assert len(read_rules) == 0, read_rules
