"""
Parse tabular precinct-level results.
"""
import requests
import json
from lxml import html


def get_precincts_for_ward(ward):
    tmpl = 'http://www.chicagoelections.com/en/pctlevel3.asp?Ward=%d&elec_code=%s&race_number=%d'
    precincts = []
    # The 2015 mayoral primary code
    election_code = 10
    # Mayoral (primary?) race number
    race_number = 10
    precinct = {}

    text = requests.get(tmpl % (ward, election_code, race_number)).text
    for tr_idx, tr in enumerate(html.fromstring(text).xpath('/html/body/table[1]/tr')):
        if tr_idx == 0:
            # This is a blank row, so skip
            headers = []
            continue
        if precinct:
            precincts.append(precinct)
        precinct = {}
        for td_idx, td in enumerate(tr.xpath('td')):
            if tr_idx == 1:
                # This is the header row
                headers.append(td.text_content().strip())
            elif td_idx == 0:
                if td.text_content() == 'Total':
                    # We're done, so exit
                    return precincts
                else:
                    precinct['id'] = '%02d%03d' % (ward, int(td.text_content().strip()))
            elif headers[td_idx] == '%':
                continue
            else:
                try:
                    precinct[headers[td_idx]] = int(td.text_content().strip())
                except:
                    print 'Error with line %d, col %d (%s)' % (tr_idx, td_idx, headers[td_idx])
                    precinct[headers[td_idx]] = 0

if __name__ == '__main__':
    precincts = []
    for ward in range(1, 51):
        precincts.extend(get_precincts_for_ward(ward))
    print json.dumps(precincts)
