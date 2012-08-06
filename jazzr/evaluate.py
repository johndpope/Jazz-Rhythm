from jazzr.rhythm.parsers import *
from jazzr.models import *
from jazzr.tools import commandline
import random, pickle, datetime, os

def load():
  files = sorted(os.listdir('results'))
  choice = commandline.menu('Choose', files)
  if choice != -1:
    f = open('results/{0}'.format(files[choice]), 'rb')
    return pickle.load(f)

def evaluate(corpus, nfolds=10, n=20, measures=2, noise=False):
  folds = getFolds(corpus, folds=nfolds)
  results = []
  i = 1
  allowed = treeconstraints.train(corpus)
  for trainset, testset in folds:
    print 'Fold {0}'.format(i)
    i += 1
    
    # Train a parser
    if noise:
      parser = StochasticParser(trainset, n=n, expressionModel=expression.additive_noise(0.1))
      #parser.beam = 0.01
    else:
      parser = StochasticParser(trainset, n=n, expressionModel=expression.train(trainset))
      #parser.beam = 0.01
    parser.allowed = allowed
    # Get the first few bars from a piece
    tests, labels = getTests(testset, measures=measures)
    annot = [x[0] for x in testset]
    for test, label, annotation in zip(tests, labels, annot):
      print annotation.name
      if len(test) <= 2:
        print 'Skipping too short test'
        continue
      parses = parser.parse_onsets(test)
      if len(parses) > 0:
        results.append((parses[0], label))
        precision, recall = measure(results[-1:])
        print 'Precision {0} recall {1}.'.format(precision, recall)
        precision, recall = measure(results)
        print 'Averages: precision {0} recall {1}.'.format(precision, recall)
        
  time = str(datetime.datetime.now())
  f = open('results/results_{0}_measures={1}_n={2}_folds={3}'.format(time, measures, n, nfolds), 'wb')
  pickle.dump(results, f)
  return results

def measure(results):
  tp = fp = tn = fn = 0.0
  for parse, label in results:
    tpx, fpx, tnx, fnx = downbeat_detection(parse, label)
    tp += tpx
    fp += fpx
    tn += tnx
    fn += fnx
  precision = recall = 0
  if tp + fp != 0:
    precision = tp/float(tp + fp)
  if tp + fn != 0:
    recall = tp/float(tp + fn)
  return precision, recall

def precision(parse, label):
  tp, fp, tnl, fn = downbeat_detection(parse, label)
  precision = 0
  if tp + fp != 0:
    precision = tp/float(tp + fp)
  return precision

def recall(parse, label):
  tp, fp, tn, fn = downbeat_detection(parse, label)
  recall = 0
  if tp + fn != 0:
    recall = tp/float(tp + fn)
  return recall
  

def getTests(testset, measures=2):
  tests = []
  labels = []
  for test, label in testset:
    onsets = []
    bar = None
    for i in range(len(test)):
      if test.type(i) in [Annotation.NOTE, Annotation.END, Annotation.SWUNG]:
        onsets.append(test.perf_onset(i))
        if bar == None:
          bar = test.bar(test.position(i))
        else:
          if test.bar(test.position(i)) >= bar + measures:
            break
    tests.append(onsets)
    labels.append(label)
  return tests, labels

ONSET = 0
TIE = 1

def symbol_to_list(S, level=0, beat=0, ties=False, division=[1]):
  treelist = []
  if S.isSymbol():
    for child, beat in zip(S.children, range(len(S.children))):
      treelist += symbol_to_list(child, level=level+1, beat=beat, ties=ties, division=division+[len(S.children)])
  elif S.isOnset():
    treelist.append((ONSET, beat, level, division))
  elif S.isTie() and ties:
    treelist.append((TIE, beat, level, division))
  return treelist

def downbeat_detection(parse, correctparse):
  results = symbol_to_list(parse)
  labels = symbol_to_list(correctparse)
  n = 0
  tp = 0
  fp = 0
  tn = 0
  fn = 0
  #for i in range(len(results)):
  #  print results[i], labels[i]
  for i in range(len(results)):
    type, beat, level, division = results[i]
    ltype, lbeat, llevel, division = labels[i]
    if type == ONSET and beat == 0:
      if beat == lbeat:
        tp += 1
      else:
        fp += 1 
    elif type == ONSET:
      if lbeat != 0:
        tn += 1
      else:
        fn += 1 
  precision = recall = 0
  if tp + fp != 0:
    precision = tp/float(tp + fp)
  if tp + fn != 0:
    recall = tp/float(tp + fn)
  return tp, fp, tn, fn

def getFolds(corpus, folds=5):
  n = len(corpus)
  results = []
  for i in range(folds):
    trainset = []
    testset = []
    n_test = int(n/float(folds))
    for j in range(n_test):
      index = int(random.random() * (n-j))
      testset += [corpus[index]]
      del corpus[index]
    trainset = corpus
    results.append((trainset, testset))
    corpus = trainset + testset
  return results

def getSubTree(notes, parse):
  if parse.isSymbol():
    childContains = False
    for child in parse.children:
      if contains(notes, getNotes(child, performance=True)):
        childContains = True
        res = getSubTree(notes, child)
        if res != None:
          return res
      if not childContains:
        return parse
  return None

def getNotes(S, performance=False):
  notes = []
  if S.isSymbol():
    for child in S.children:
      notes += getNotes(child, performance=performance)
  elif S.isOnset():
    if performance:
      return [S.annotation.perf_onset(S.index)]
    else:
      return [S.on]
  return notes

def contains(small, big):
  for i in xrange(len(big)-len(small)+1):
    for j in xrange(len(small)):
      if big[i+j] != small[j]:
        break
      else:
        return i, i+len(small)
  return False
