import os.path
from unittest import TestCase

import responses

from chi_elections.summary import (FixedWidthField, ResultParser, SummaryClient,
        SummaryParser)

TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    'data')
SUMMARY_TEST_FILENAME = os.path.join(TEST_DATA_DIR, 'results', 'ap',
    'summary.txt')

class ParserTestCase(TestCase):

    def setUp(self):
        self.parser = SummaryParser()

    def test_parse(self):
        with open(SUMMARY_TEST_FILENAME, 'r') as f:
            self.parser.parse(f.read())
            self.assertEqual(len(self.parser.races), 98)

            mayor = next(r for r in self.parser.races if r.name == "Mayor")
            self.assertEqual(len(mayor.candidates), 5)

            rahm = next(c for c in mayor.candidates
                        if c.full_name == "RAHM EMANUEL")
            self.assertEqual(rahm.vote_total, 0)

           
class FixedWidthFieldTestCase(TestCase):
    def test_parse(self):
        line = "0010001206900000000000NON       Mayor                                                   RAHM EMANUEL                          City Of Chicago          001"
        field = FixedWidthField(0, 3, transform=int)
        parsed = field.parse(line)
        self.assertEqual(parsed, 1)
        field = FixedWidthField(22, 3)
        parsed = field.parse(line)
        self.assertEqual(parsed, "NON")
        field = FixedWidthField(32, 56)
        parsed = field.parse(line)
        self.assertEqual(parsed, "Mayor")



class ResultParserTestCase(TestCase):
    def test_parse_line(self):
        parser = ResultParser()
        line = "0010001206900000000000NON       Mayor                                                   RAHM EMANUEL                          City Of Chicago          001"
        result = parser.parse_line(line)
        self.assertEqual(result['contest_code'], 10)
        self.assertEqual(result['candidate_number'], 1)
        self.assertEqual(result['precincts_total'], 2069)
        self.assertEqual(result['vote_total'], 0)
        self.assertEqual(result['precincts_reporting'], 0)
        self.assertEqual(result['party'], "NON")
        self.assertEqual(result['race_name'], "Mayor")
        self.assertEqual(result['candidate_name'], "RAHM EMANUEL")
        self.assertEqual(result['reporting_unit_name'], "City Of Chicago")
        self.assertEqual(result['vote_for'], 1)

    def test_parse_line_no_text(self):
        parser = ResultParser()
        line = "0010001206900000000000"
        result = parser.parse_line(line)
        self.assertEqual(result['contest_code'], 10)
        self.assertEqual(result['candidate_number'], 1)
        self.assertEqual(result['precincts_total'], 2069)
        self.assertEqual(result['vote_total'], 0)
        self.assertEqual(result['precincts_reporting'], 0)
        self.assertEqual(result['party'], "")
        self.assertEqual(result['race_name'], "")
        self.assertEqual(result['candidate_name'], "")
        self.assertEqual(result['reporting_unit_name'], "")
        self.assertEqual(result['vote_for'], None)


class SummaryClientTestCase(TestCase):
    @responses.activate
    def test_fetch(self):
        client = SummaryClient()
        with open(SUMMARY_TEST_FILENAME) as f:
            response_body = f.read()
            responses.add(responses.GET, client.get_url(), body=response_body,
                content_type='text/plain')    
            client.fetch() 
            self.assertEqual(len(client.races), 98)

            mayor = next(r for r in client.races if r.name == "Mayor")
            self.assertEqual(len(mayor.candidates), 5)

            rahm = next(c for c in mayor.candidates
                        if c.full_name == "RAHM EMANUEL")
            self.assertEqual(rahm.vote_total, 0)
