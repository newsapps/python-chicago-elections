chi-elections
=============

chi-elections is a Python package for loading and parsing election results from the [Chicago Board of Elections](http://www.chicagoelections.com/).

Summary Results
---------------

The Board of Elections provides election-night results at a racewide level.  The file lives at 

http://www.chicagoelections.com/results/ap/summary.txt

before election day, for testing.

It lives at

http://www.chicagoelections.com/ap/summary.txt

on election night.

To access the results:

    from chi_elections import SummaryClient
    
    client = SummaryClient()
    client.fetch()
    mayor = next(r for r in client.races if r.name == "Mayor")
    self.assertEqual(len(mayor.candidates), 5)

    rahm = next(c for c in mayor.candidates
                if c.full_name == "RAHM EMANUEL")
    print(rahm.vote_total)

If you want to specify an alternate url, for example the test URL, pass it to the constructor of `SummaryClient`:

    client = SummaryClient(url='http://www.chicagoelections.com/results/ap/summary.txt')
