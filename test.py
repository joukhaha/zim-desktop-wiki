#!/usr/bin/python

# -*- coding: utf8 -*-

# Copyright 2008 Jaap Karssenberg <pardus@cpan.org>

import os
import sys
import shutil
import getopt
import logging

import unittest
import time
import types

import tests

# TODO overload one of the unittest classes to test add file names

pyfiles = []
for d, dirs, files in os.walk('zim'):
	pyfiles.extend([d+'/'+f for f in files if f.endswith('.py')])
pyfiles.sort()

class FastTestLoader(unittest.TestLoader):
	'''Extension of TestLoader which ignores all classes which have an
	attribute 'slowTest' set to True.
	'''

	def __init__(self, full=True):
		unittest.TestLoader.__init__(self)
		self.ignored = 0
		self.full = full

	def loadTestsFromModule(self, module):
		"""Return a suite of all tests cases contained in the given module"""
		tests = []
		for name in dir(module):
			obj = getattr(module, name)
			if (isinstance(obj, (type, types.ClassType)) and
				issubclass(obj, unittest.TestCase)):
				if not self.full and hasattr(obj, 'slowTest') and obj.slowTest:
					print 'Ignoring slow test:', obj.__name__
					self.ignored += 1
				else:
					tests.append(self.loadTestsFromTestCase(obj))
		return self.suiteClass(tests)


class MyTextTestRunner(unittest.TextTestRunner):
	'''Extionsion of TextTestRunner to report number of ignored tests in the
	proper place.
	'''

	def __init__(self, verbosity, ignored):
		unittest.TextTestRunner.__init__(self, verbosity=verbosity)
		self.ignored = ignored

	def run(self, test):
		"Run the given test case or test suite."
		result = self._makeResult()
		startTime = time.time()
		test(result)
		stopTime = time.time()
		timeTaken = stopTime - startTime
		result.printErrors()
		self.stream.writeln(result.separator2)
		run = result.testsRun
		self.stream.writeln("Ran %d test%s in %.3fs" %
							(run, run != 1 and "s" or "", timeTaken))
		ignored = self.ignored
		if ignored > 0:
			self.stream.writeln("Ignored %d slow test%s" %
							(ignored, ignored != 1 and "s" or ""))
		self.stream.writeln()
		if not result.wasSuccessful():
			self.stream.write("FAILED (")
			failed, errored = map(len, (result.failures, result.errors))
			if failed:
				self.stream.write("failures=%d" % failed)
			if errored:
				if failed: self.stream.write(", ")
				self.stream.write("errors=%d" % errored)
			self.stream.writeln(")")
		else:
			self.stream.writeln("OK")
		return result



def main(argv=None):
	'''Run either all tests, or those specified in argv'''
	if argv is None:
		argv = sys.argv

	# parse options
	coverage = None
	full = False
	opts, args = getopt.gnu_getopt(argv[1:], 'h', ['help', 'coverage', 'full'])
	for o, a in opts:
		if o in ('-h', '--help'):
			print '''\
usage: %s [OPTIONS] [MODULES]

Where MODULE should a module name from ./tests/
If no module is given the whole test suite is run.

Options:
  -h, --help   print this text
  --full       run all tests (much slower that base set)
  --coverage   report test coverage statistics
''' % argv[0]
			return
		elif o == '--coverage':
			try:
				import coverage as coverage_module
			except ImportError:
				print >>sys.stderr, '''\
Can not run test coverage without module coverage.
On Ubuntu or Debian install package 'python-coverage'.
'''
				sys.exit(1)
			coverage = coverage_module
			coverage.erase() # clean up old date set
			coverage.exclude('assert')
			coverage.exclude('raise NotImplementedError')
			coverage.start()
		elif o == '--full':
			full = True
		else:
			assert False

	# Set logging handler
	level = logging.WARNING
	logging.basicConfig(level=level, format='%(levelname)s: %(message)s')

	# Collect the test cases
	suite = unittest.TestSuite()
	loader = FastTestLoader(full=full)

	if args:
		modules = [ 'tests.'+name for name in args ]
	else:
		suite.addTest(TestCompileAll())
		modules = [ 'tests.'+name for name in tests.__all__ ]

	for name in modules:
		test = loader.loadTestsFromName(name)
		suite.addTest(test)

	# And run them
	MyTextTestRunner(verbosity=3, ignored=loader.ignored).run(suite)

	if coverage:
		coverage.stop()
		report_coverage(coverage)


def report_coverage(coverage):
	print ''
	print 'Writing detailed coverage reports...'
	coverage.report(pyfiles, show_missing=False)

	# Detailed report in html
	if os.path.exists('coverage/'):
		import shutil
		shutil.rmtree('coverage/') # cleanup
	os.mkdir('coverage')

	index = []
	for path in pyfiles:
		if '_lib' in path or '_version' in path: continue
		htmlfile = path[:-3].replace('/', '.')+'.html'
		html = open('coverage/'+htmlfile, 'w')
		html.write('''\
<html>
<head>
<title>Coverage report for %s</title>
<style>
	.code { white-space: pre; font-family: monospace }
	.executed { background-color: #9f9 }
	.excluded { background-color: #ccc }
	.missing  { background-color: #f99 }
	.comment  { }
</style>
</head>
<body>
<h1>Coverage report for %s</h1>
<table width="100%%">
<tr><td class="executed">&nbsp;</td><td>Executed statement</td></tr>
<tr><td class="missing">&nbsp;</td><td>Untested statement</td></tr>
<tr><td class="excluded">&nbsp;</td><td>Ignored statement</td></tr>
<tr><td>&nbsp</td><td>&nbsp</td></tr>
''' % (path, path))


		p, statements, excluded, missing, l = coverage.analysis2(path)
		nstat = len(statements)
		nexec = nstat - len(missing)
		index.append((path, htmlfile, nstat, nexec))
		file = open(path)
		i = 0
		for line in file:
			i += 1
			line = line.replace('<', '&lt;')
			line = line.replace('>', '&gt;')
			if   i in missing: type = 'missing'
			elif i in excluded: type = 'excluded'
			elif i in statements: type = 'executed'
			else: type = 'comment'

			html.write('<tr><td class="%s">%i</td><td class="code">%s</td></tr>\n'
							% (type, i, line.rstrip()) )
		html.write('''\
</table>
</body>
</html>
''')

	# Index for detailed reports
	html = open('coverage/index.html', 'w')
	html.write('''\
<html>
<head>
<title>Test Coverage Index</title>
<style>
	.good  { background-color: #9f9; text-align: right }
	.close { background-color: #ff9; text-align: right }
	.bad   { background-color: #f99; text-align: right }
	.int   { text-align: right }
</style>
</head>
<body>
<h1>Test Coverage Index</h1>
<table>
<tr><td><b>File</b></td><td><b>Stmts</b></td><td><b>Exec</b></td><td><b>Cover</b></td></tr>
''')

	total_stat = reduce(int.__add__, [r[2] for r in index])
	total_exec = reduce(int.__add__, [r[3] for r in index])
	total_perc = int( float(total_exec) / total_stat * 100 )
	if total_perc == 100: type = 'good'
	elif total_perc > 80: type = 'close'
	else: type = 'bad'
	html.write('<tr><td><b>Total</b></td>'
		       '<td class="int">%i</td><td class="int">%i</td>'
			   '<td class="%s">%.0f%%</td></tr>\n'
				   % (total_stat, total_exec, type, total_perc) )

	for report in index:
		pyfile, htmlfile, statements, executed = report
		if statements: percentage = int( float(executed) / statements * 100 )
		else: percentage = 100
		if percentage == 100: type = 'good'
		elif percentage > 80: type = 'close'
		else: type = 'bad'
		html.write('<tr><td><a href="%s">%s</a></td>'
		           '<td class="int">%i</td><td class="int">%i</td>'
				   '<td class="%s">%.0f%%</td></tr>\n'
				   % (htmlfile, pyfile, statements, executed, type, percentage) )
	html.write('''\
</table>
</body>
</html>
''')

	print '\nDetailed coverage reports can be found in ./coverage/'


class TestCompileAll(unittest.TestCase):

	def runTest(self):
		'''Test if all modules compile'''
		for file in pyfiles:
			module = file[:-3].replace('/', '.')
			assert __import__(module)


if __name__ == '__main__':
	main()
