#!/usr/bin/env python3

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from pico8.lua import lexer
from pico8.lua import parser


LUA_SAMPLE = '''
-- game of life: v1
-- by dddaaannn

alive_color = 7; width = 128; height = 128

board_i = 1
boards = {{}, {}}

cls()
for y=1,height do
  boards[1][y] = {}
  boards[2][y] = {}
  for x=1,width do
    boards[1][y][x] = 0
    boards[2][y][x] = 0
  end
end
  
-- draw an r pentomino
boards[1][60][64] = 1
boards[1][60][65] = 1
boards[1][61][63] = 1
boards[1][61][64] = 1
boards[1][62][64] = 1

function get(bi,x,y)
  if ((x < 1) or (x > width) or (y < 1) or (y > height)) then
    return 0
  end
  return boards[bi][y][x]
end

while true do
  for y=1,height do
    for x=1,width do
      pset(x-1,y-1,boards[board_i][y][x] * alive_color)
    end
  end
  flip()

  other_i = (board_i % 2) + 1
  for y=1,height do
    for x=1,width do       
      neighbors = (
        get(board_i,x-1,y-1) +
        get(board_i,x,y-1) +
        get(board_i,x+1,y-1) +
        get(board_i,x-1,y) +
        get(board_i,x+1,y) +
        get(board_i,x-1,y+1) +
        get(board_i,x,y+1) +
        get(board_i,x+1,y+1))
      if ((neighbors == 3) or
          ((boards[board_i][y][x] == 1) and neighbors == 2)) then
        boards[other_i][y][x] = 1
      else
        boards[other_i][y][x] = 0
      end
    end
  end
  board_i = other_i
end
'''


def get_tokens(s):
    lxr = lexer.Lexer(version=4)
    lxr.process_lines([(l + '\n') for l in s.split('\n')])
    return lxr.tokens


def get_parser(s):
    p = parser.Parser(version=4)
    p._tokens = get_tokens(s)
    p._pos = 0
    return p
    

class TestParser(unittest.TestCase):
    def testParserErrorMsg(self):
        # coverage
        txt = str(parser.ParserError(
            'msg', lexer.Token('x', lineno=1, charno=2)))

    def testCursorPeek(self):
        p = get_parser('break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual(0, p._pos)
        self.assertEqual('break', p._peek().value)
        self.assertEqual(0, p._pos)

    def testCursorAccept(self):
        p = get_parser('break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual(0, p._pos)
        self.assertIsNone(p._accept(lexer.TokName))
        self.assertIsNone(p._accept(lexer.TokKeyword('and')))
        self.assertIsNotNone(p._accept(lexer.TokKeyword('break')))
        self.assertEqual(1, p._pos)
        self.assertIsNotNone(p._accept(lexer.TokName))
        self.assertIsNotNone(p._accept(lexer.TokNumber))
        self.assertIsNotNone(p._accept(lexer.TokString))
        self.assertIsNotNone(p._accept(lexer.TokSymbol('==')))
        self.assertEqual(11, p._pos)

    def testCursorAcceptStopsAtMaxPos(self):
        p = get_parser('break name 7.42 -- Comment text\n"string literal" ==')
        p._max_pos = 4
        self.assertEqual(0, p._pos)
        self.assertIsNone(p._accept(lexer.TokName))
        self.assertIsNone(p._accept(lexer.TokKeyword('and')))
        self.assertIsNotNone(p._accept(lexer.TokKeyword('break')))
        self.assertEqual(1, p._pos)
        self.assertIsNotNone(p._accept(lexer.TokName))
        self.assertIsNone(p._accept(lexer.TokNumber))
        self.assertIsNone(p._accept(lexer.TokString))
        self.assertIsNone(p._accept(lexer.TokSymbol('==')))
        self.assertEqual(3, p._pos)

    def testCursorExpect(self):
        p = get_parser('break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual(0, p._pos)
        self.assertRaises(parser.ParserError,
                          p._expect, lexer.TokKeyword('and'))
        self.assertEqual(0, p._pos)
        tok_break = p._expect(lexer.TokKeyword('break'))
        self.assertEqual('break', tok_break.value)
        self.assertEqual(1, p._pos)
        tok_name = p._expect(lexer.TokName)
        self.assertEqual('name', tok_name.value)
        self.assertEqual(3, p._pos)  # "break, space, name"

    def testAssert(self):
        p = get_parser('break name 7.42 -- Comment text\n"string literal" ==')
        self.assertEqual('DUMMY', p._assert('DUMMY', 'test assert'))
        try:
            p._assert(None, 'test assert')
            self.fail()
        except parser.ParserError as e:
            self.assertEqual('test assert', e.msg)
            self.assertEqual('break', e.token.value)

    def testNameListOneOK(self):
        p = get_parser('name1')
        node = p._namelist()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.NameList))
        self.assertEqual('name1', node.names[0].value)
        self.assertEqual(1, len(node.names))

    def testNameListOneWithMoreOK(self):
        p = get_parser('name1 + name2')
        node = p._namelist()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.NameList))
        self.assertEqual('name1', node.names[0].value)
        self.assertEqual(1, len(node.names))

    def testNameListMultipleOK(self):
        p = get_parser('name1,name2,   name3, name4')
        node = p._namelist()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.NameList))
        self.assertEqual(9, p._pos)
        self.assertEqual(4, len(node.names))
        self.assertEqual('name1', node.names[0].value)
        self.assertEqual('name2', node.names[1].value)
        self.assertEqual('name3', node.names[2].value)
        self.assertEqual('name4', node.names[3].value)
        
    def testNameListErr(self):
        p = get_parser('123.45 name1')
        node = p._namelist()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)
    
    def testExpValueNil(self):
        p = get_parser('nil')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertEqual(None, node.value)

    def testExpValueFalse(self):
        p = get_parser('false')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertEqual(False, node.value)

    def testExpValueTrue(self):
        p = get_parser('true')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertEqual(True, node.value)

    def testExpValueNumber(self):
        p = get_parser('123.45')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertTrue(node.value.matches(lexer.TokNumber('123.45')))
        
    def testExpValueString(self):
        p = get_parser('"string literal"')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpValue))
        self.assertTrue(node.value.matches(lexer.TokString('string literal')))
        
    def testExpValueDots(self):
        p = get_parser('...')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.VarargDots))

    def testExpValueErr(self):
        p = get_parser('break')
        node = p._exp()
        self.assertIsNone(node)

    def testExpUnOpHash(self):
        p = get_parser('#foo')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpUnOp))
        self.assertEqual('#', node.unop.value)
        self.assertTrue(isinstance(node.exp.value, parser.VarName))
        self.assertEqual(lexer.TokName('foo'), node.exp.value.name)

    def testExpUnOpMinus(self):
        p = get_parser('-45')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertTrue(isinstance(node, parser.ExpUnOp))
        self.assertEqual('-', node.unop.value)
        self.assertTrue(isinstance(node.exp, parser.ExpValue))
        self.assertTrue(node.exp.value.matches(lexer.TokNumber('45')))

    def testExpBinOp(self):
        p = get_parser('1 + 2')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(5, p._pos)
        
    def testExpBinOpChain(self):
        p = get_parser('1 + 2 * 3 - 4 / 5..6^7 > 8 != foo')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(29, p._pos)
        self.assertEqual('foo', node.exp2.value.name.value)
        self.assertEqual('!=', node.binop.value)
        self.assertTrue(node.exp1.exp2.value.matches(lexer.TokNumber('8')))
        self.assertEqual('>', node.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp2.value.matches(lexer.TokNumber('7')))
        self.assertEqual('^', node.exp1.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp1.exp2.value.matches(lexer.TokNumber('6')))
        self.assertEqual('..', node.exp1.exp1.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp1.exp1.exp2.value.matches(lexer.TokNumber('5')))
        self.assertEqual('/', node.exp1.exp1.exp1.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp1.exp1.exp1.exp2.value.matches(lexer.TokNumber('4')))
        self.assertEqual('-', node.exp1.exp1.exp1.exp1.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp1.exp1.exp1.exp1.exp2.value.matches(lexer.TokNumber('3')))
        self.assertEqual('*', node.exp1.exp1.exp1.exp1.exp1.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp1.exp1.exp1.exp1.exp1.exp2.value.matches(lexer.TokNumber('2')))
        self.assertEqual('+', node.exp1.exp1.exp1.exp1.exp1.exp1.exp1.binop.value)
        self.assertTrue(node.exp1.exp1.exp1.exp1.exp1.exp1.exp1.exp1.value.matches(lexer.TokNumber('1')))

    def testExpList(self):
        p = get_parser('1, 2, 3 - 4, 5..6^7, foo')
        node = p._explist()
        self.assertIsNotNone(node)
        self.assertEqual(21, p._pos)
        self.assertEqual(5, len(node.exps))
        self.assertTrue(node.exps[0].value.matches(lexer.TokNumber('1')))
        self.assertTrue(node.exps[1].value.matches(lexer.TokNumber('2')))
        self.assertTrue(node.exps[2].exp1.value.matches(lexer.TokNumber('3')))
        self.assertEqual('-', node.exps[2].binop.value)
        self.assertTrue(node.exps[2].exp2.value.matches(lexer.TokNumber('4')))
        self.assertTrue(node.exps[3].exp1.exp1.value.matches(lexer.TokNumber('5')))
        self.assertEqual('..', node.exps[3].exp1.binop.value)
        self.assertTrue(node.exps[3].exp1.exp2.value.matches(lexer.TokNumber('6')))
        self.assertEqual('^', node.exps[3].binop.value)
        self.assertTrue(node.exps[3].exp2.value.matches(lexer.TokNumber('7')))
        self.assertEqual('foo', node.exps[4].value.name.value)

    def testExpListErr(self):
        p = get_parser('break')
        node = p._explist()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)

    def testExpListIncompleteErr(self):
        p = get_parser('1, 2,')
        self.assertRaises(parser.ParserError,
                          p._explist)

    def testPrefixExpName(self):
        p = get_parser('foo')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        
    def testPrefixExpParenExp(self):
        p = get_parser('(2 + 3)')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertTrue(isinstance(node, parser.ExpBinOp))
        self.assertTrue(node.exp1.value.matches(lexer.TokNumber('2')))
        self.assertEqual('+', node.binop.value)
        self.assertTrue(node.exp2.value.matches(lexer.TokNumber('3')))
        
    def testPrefixExpIndex(self):
        p = get_parser('foo[4 + 5]')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(8, p._pos)
        self.assertTrue(isinstance(node, parser.VarIndex))
        self.assertEqual('foo', node.exp_prefix.name.value)
        self.assertTrue(node.exp_index.exp1.value.matches(lexer.TokNumber('4')))
        self.assertEqual('+', node.exp_index.binop.value)
        self.assertTrue(node.exp_index.exp2.value.matches(lexer.TokNumber('5')))
        
    def testPrefixExpAttribute(self):
        p = get_parser('foo.bar')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node, parser.VarAttribute))
        self.assertEqual('foo', node.exp_prefix.name.value)
        self.assertEqual('bar', node.attr_name.value)

    def testPrefixExpChain(self):
        p = get_parser('(1+2)[foo].bar.baz')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(12, p._pos)
        self.assertTrue(isinstance(node, parser.VarAttribute))
        self.assertEqual('baz', node.attr_name.value)
        self.assertTrue(isinstance(node.exp_prefix, parser.VarAttribute))
        self.assertEqual('bar', node.exp_prefix.attr_name.value)
        self.assertTrue(isinstance(node.exp_prefix.exp_prefix, parser.VarIndex))
        self.assertEqual('foo', node.exp_prefix.exp_prefix.exp_index.value.name.value)
        self.assertTrue(isinstance(node.exp_prefix.exp_prefix.exp_prefix, parser.ExpBinOp))
        self.assertTrue(node.exp_prefix.exp_prefix.exp_prefix.exp1.value.matches(lexer.TokNumber('1')))
        self.assertEqual('+', node.exp_prefix.exp_prefix.exp_prefix.binop.value)
        self.assertTrue(node.exp_prefix.exp_prefix.exp_prefix.exp2.value.matches(lexer.TokNumber('2')))

    def testFuncname(self):
        p = get_parser('foo')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual('foo', node.namepath[0].value)
        self.assertIsNone(node.methodname)

    def testFuncnameErr(self):
        p = get_parser('123')
        node = p._funcname()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)
        
    def testFuncnamePath(self):
        p = get_parser('foo.bar.baz')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(5, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual('foo', node.namepath[0].value)
        self.assertEqual('bar', node.namepath[1].value)
        self.assertEqual('baz', node.namepath[2].value)
        self.assertIsNone(node.methodname)
        
    def testFuncnameMethod(self):
        p = get_parser('foo:method')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual('foo', node.namepath[0].value)
        self.assertEqual('method', node.methodname.value)

    def testFuncnamePathAndMethod(self):
        p = get_parser('foo.bar.baz:method')
        node = p._funcname()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertTrue(isinstance(node, parser.FunctionName))
        self.assertEqual('foo', node.namepath[0].value)
        self.assertEqual('bar', node.namepath[1].value)
        self.assertEqual('baz', node.namepath[2].value)
        self.assertEqual('method', node.methodname.value)
    
    def testArgsExpList(self):
        p = get_parser('(foo, bar, baz)')
        node = p._args()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertEqual(3, len(node.explist.exps))
        
    def testArgsString(self):
        p = get_parser('"string literal"')
        node = p._args()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(node.matches(lexer.TokString('string literal')))
    
    def testArgsNone(self):
        p = get_parser('')
        node = p._args()
        self.assertIsNone(node)
    
    def testPrefixExpFunctionCall(self):
        p = get_parser('fname(foo, bar, baz)')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        self.assertEqual('fname', node.exp_prefix.name.value)
        self.assertEqual(3, len(node.args.explist.exps))

    def testPrefixExpFunctionCallValueArgs(self):
        p = get_parser('fname(1, 2, 3)')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)

    def testPrefixExpFunctionCallNoArgs(self):
        p = get_parser('fname()')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        
    def testPrefixExpFunctionCallMethod(self):
        p = get_parser('obj:method(foo, bar, baz)')
        node = p._prefixexp()
        self.assertIsNotNone(node)
        self.assertEqual(12, p._pos)
        self.assertEqual('obj', node.exp_prefix.name.value)
        self.assertEqual('method', node.methodname.value)
        self.assertEqual(3, len(node.args.explist.exps))
        
    def testFunctionCall(self):
        p = get_parser('fname(foo, bar, baz)')
        node = p._functioncall()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        self.assertEqual('fname', node.exp_prefix.name.value)
        self.assertEqual(3, len(node.args.explist.exps))

    def testFunctionCallValueArgs(self):
        p = get_parser('foo(1, 2, 3)')
        node = p._functioncall()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)

    def testFunctionCallNoArgs(self):
        p = get_parser('foo()')
        node = p._functioncall()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)

    def testFunctionCallMethod(self):
        p = get_parser('obj:method(foo, bar, baz)')
        node = p._functioncall()
        self.assertIsNotNone(node)
        self.assertEqual(12, p._pos)
        self.assertEqual('obj', node.exp_prefix.name.value)
        self.assertEqual('method', node.methodname.value)
        self.assertEqual(3, len(node.args.explist.exps))

    def testFunctionCallErr(self):
        p = get_parser('foo + 7')
        node = p._functioncall()
        self.assertIsNone(node)
        self.assertEqual(0, p._pos)

    def testExpValuePrefixExp(self):
        p = get_parser('foo.bar')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node.value, parser.VarAttribute))
        self.assertEqual('foo', node.value.exp_prefix.name.value)
        self.assertEqual('bar', node.value.attr_name.value)
    
    def testFieldExpKey(self):
        p = get_parser('[1] = 2')
        node = p._field()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertTrue(isinstance(node, parser.FieldExpKey))
        self.assertTrue(node.key_exp.value.matches(lexer.TokNumber('1')))
        self.assertTrue(node.exp.value.matches(lexer.TokNumber('2')))
        
    def testFieldNamedKey(self):
        p = get_parser('foo = 3')
        node = p._field()
        self.assertIsNotNone(node)
        self.assertEqual(5, p._pos)
        self.assertTrue(isinstance(node, parser.FieldNamedKey))
        self.assertEqual('foo', node.key_name.value)
        self.assertTrue(node.exp.value.matches(lexer.TokNumber('3')))
        
    def testFieldExp(self):
        p = get_parser('foo')
        node = p._field()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.FieldExp))
        self.assertEqual('foo', node.exp.value.name.value)
        
    def testTableConstructor(self):
        p = get_parser('{[1]=2,foo=3;4}')
        node = p._tableconstructor()
        self.assertIsNotNone(node)
        self.assertEqual(13, p._pos)
        self.assertTrue(isinstance(node, parser.TableConstructor))
        self.assertEqual(3, len(node.fields))

        self.assertTrue(isinstance(node.fields[0], parser.FieldExpKey))
        self.assertTrue(node.fields[0].key_exp.value.matches(lexer.TokNumber('1')))
        self.assertTrue(node.fields[0].exp.value.matches(lexer.TokNumber('2')))

        self.assertTrue(isinstance(node.fields[1], parser.FieldNamedKey))
        self.assertEqual('foo', node.fields[1].key_name.value)
        self.assertTrue(node.fields[1].exp.value.matches(lexer.TokNumber('3')))

        self.assertTrue(isinstance(node.fields[2], parser.FieldExp))
        self.assertTrue(node.fields[2].exp.value.matches(lexer.TokNumber('4')))

    def testTableConstructorTrailingSep(self):
        p = get_parser('{5,}')
        node = p._tableconstructor()
        self.assertIsNotNone(node)
        self.assertEqual(4, p._pos)
        self.assertEqual(1, len(node.fields))
        self.assertTrue(node.fields[0].exp.value.matches(lexer.TokNumber('5')))

    def testTableConstructorEmpty(self):
        p = get_parser('{   }')
        node = p._tableconstructor()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertTrue(isinstance(node, parser.TableConstructor))
        self.assertEqual([], node.fields)
        
    def testExpValueTableConstructor(self):
        p = get_parser('{5,}')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(4, p._pos)
        self.assertEqual(1, len(node.value.fields))
        self.assertTrue(node.value.fields[0].exp.value.matches(lexer.TokNumber('5')))
        
    def testArgsTableConstructor(self):
        p = get_parser('{5,}')
        node = p._args()
        self.assertIsNotNone(node)
        self.assertEqual(4, p._pos)
        self.assertEqual(1, len(node.fields))
        self.assertTrue(node.fields[0].exp.value.matches(lexer.TokNumber('5')))

    def testFuncBodyEmptyParList(self):
        p = get_parser('() return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(6, p._pos)
        self.assertEqual(None, node.parlist)
        self.assertEqual(None, node.dots)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatReturn))

    def testFuncBodyParList(self):
        p = get_parser('(foo, bar) return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        self.assertEqual(2, len(node.parlist.names))
        self.assertEqual('foo', node.parlist.names[0].value)
        self.assertEqual('bar', node.parlist.names[1].value)
        self.assertEqual(None, node.dots)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatReturn))

    def testFuncBodyParListWithDots(self):
        p = get_parser('(foo, bar, ...) return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(13, p._pos)
        self.assertEqual(2, len(node.parlist.names))
        self.assertEqual('foo', node.parlist.names[0].value)
        self.assertEqual('bar', node.parlist.names[1].value)
        self.assertTrue(isinstance(node.dots, parser.VarargDots))
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatReturn))

    def testFuncBodyParListOnlyDots(self):
        p = get_parser('(...) return end')
        node = p._funcbody()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(None, node.parlist)
        self.assertTrue(isinstance(node.dots, parser.VarargDots))
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatReturn))

    def testFunctionNoArgs(self):
        p = get_parser('function() return end')
        node = p._function()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(None, node.funcbody.parlist)
        self.assertEqual(None, node.funcbody.dots)
        self.assertEqual(1, len(node.funcbody.block.stats))
        self.assertTrue(isinstance(node.funcbody.block.stats[0],
                                   parser.StatReturn))

    def testFunctionFancyArgs(self):
        p = get_parser('function(foo, bar, ...) return end')
        node = p._function()
        self.assertIsNotNone(node)
        self.assertEqual(14, p._pos)
        self.assertEqual(2, len(node.funcbody.parlist.names))
        self.assertEqual('foo', node.funcbody.parlist.names[0].value)
        self.assertEqual('bar', node.funcbody.parlist.names[1].value)
        self.assertTrue(isinstance(node.funcbody.dots, parser.VarargDots))
        self.assertEqual(1, len(node.funcbody.block.stats))
        self.assertTrue(isinstance(node.funcbody.block.stats[0],
                                   parser.StatReturn))
        
    def testExpValueFunction(self):
        p = get_parser('function() return end')
        node = p._exp()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(None, node.value.funcbody.parlist)
        self.assertEqual(None, node.value.funcbody.dots)
        self.assertEqual(1, len(node.value.funcbody.block.stats))
        self.assertTrue(isinstance(node.value.funcbody.block.stats[0],
                                   parser.StatReturn))
        
    def testVarName(self):
        p = get_parser('foo')
        node = p._var()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertEqual('foo', node.name.value)
        
    def testVarIndex(self):
        p = get_parser('bar[7]')
        node = p._var()
        self.assertIsNotNone(node)
        self.assertEqual(4, p._pos)
        self.assertEqual('bar', node.exp_prefix.name.value)
        self.assertTrue(node.exp_index.value.matches(lexer.TokNumber('7')))
        
    def testVarAttribute(self):
        p = get_parser('baz.bat')
        node = p._var()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertEqual('baz', node.exp_prefix.name.value)
        self.assertEqual('bat', node.attr_name.value)
    
    def testVarList(self):
        p = get_parser('foo, bar[7], baz.bat')
        node = p._varlist()
        self.assertIsNotNone(node)
        self.assertEqual(12, p._pos)
        self.assertEqual(3, len(node.vars))
        self.assertEqual('foo', node.vars[0].name.value)
        self.assertEqual('bar', node.vars[1].exp_prefix.name.value)
        self.assertTrue(node.vars[1].exp_index.value.matches(lexer.TokNumber('7')))
        self.assertEqual('baz', node.vars[2].exp_prefix.name.value)
        self.assertEqual('bat', node.vars[2].attr_name.value)

    def testLastStatBreak(self):
        p = get_parser('break')
        node = p._laststat()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.StatBreak))
        self.assertEqual(0, node._start_token_pos)
        self.assertEqual(1, node._end_token_pos)

    def testLastStatReturnNoExp(self):
        p = get_parser('return')
        node = p._laststat()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertTrue(isinstance(node, parser.StatReturn))
        self.assertIsNone(node.explist)

    def testLastStatReturnExps(self):
        p = get_parser('return 1, 2, 3')
        node = p._laststat()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertTrue(isinstance(node, parser.StatReturn))
        self.assertEqual(3, len(node.explist.exps))

    def testLastStatErr(self):
        p = get_parser('name')
        node = p._laststat()
        self.assertIsNone(node)

    def testStatAssignment(self):
        p = get_parser('foo, bar, baz = 1, 2, 3')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(17, p._pos)
        self.assertEqual(3, len(node.varlist.vars))
        self.assertEqual('foo', node.varlist.vars[0].name.value)
        self.assertEqual('bar', node.varlist.vars[1].name.value)
        self.assertEqual('baz', node.varlist.vars[2].name.value)
        self.assertTrue(node.assignop.matches(lexer.TokSymbol('=')))
        self.assertEqual(3, len(node.explist.exps))
        self.assertTrue(node.explist.exps[0].value.matches(lexer.TokNumber('1')))
        self.assertTrue(node.explist.exps[1].value.matches(lexer.TokNumber('2')))
        self.assertTrue(node.explist.exps[2].value.matches(lexer.TokNumber('3')))
        
    def testStatFunctionCall(self):
        p = get_parser('foo(1, 2, 3)')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(10, p._pos)
        self.assertEqual('foo', node.functioncall.exp_prefix.name.value)
        self.assertEqual(3, len(node.functioncall.args.explist.exps))
        self.assertTrue(node.functioncall.args.explist.exps[0].value.matches(lexer.TokNumber('1')))
        self.assertTrue(node.functioncall.args.explist.exps[1].value.matches(lexer.TokNumber('2')))
        self.assertTrue(node.functioncall.args.explist.exps[2].value.matches(lexer.TokNumber('3')))
        
    def testStatDo(self):
        p = get_parser('do break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(5, p._pos)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))
        
    def testStatWhile(self):
        p = get_parser('while true do break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertEqual(True, node.exp.value)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))
        
    def testStatWhileLiveExample(self):
        p = get_parser('\t\twhile(s.y<b.y)do\n'
                       '\t\t\ts.y+=1;e.y+=1;s.x+=dx1;e.x+=dx2;\n'
                       '\t\t\tline(s.x,s.y,e.x,e.y);\n'
                       '\t\tend\n')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(62, p._pos)
        self.assertEqual(5, len(node.block.stats))
        
    def testStatRepeat(self):
        p = get_parser('repeat break until true')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))
        self.assertEqual(True, node.exp.value)
        
    def testStatIf(self):
        p = get_parser('if true then break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertEqual(1, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))
        
    def testStatIfElse(self):
        p = get_parser('if true then break else return end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(13, p._pos)
        self.assertEqual(2, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))
        self.assertIsNone(node.exp_block_pairs[1][0])
        self.assertEqual(1, len(node.exp_block_pairs[1][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[1][1].stats[0], parser.StatReturn))
        self.assertIsNone(node.exp_block_pairs[1][1].stats[0].explist)

    def testStatIfElseIf(self):
        p = get_parser('if true then break elseif false then return end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(17, p._pos)
        self.assertEqual(2, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))
        self.assertEqual(False, node.exp_block_pairs[1][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[1][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[1][1].stats[0], parser.StatReturn))
        self.assertIsNone(node.exp_block_pairs[1][1].stats[0].explist)
        
    def testStatIfElseIfElse(self):
        p = get_parser('if true then break elseif false then break else return end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(21, p._pos)
        self.assertEqual(3, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))
        self.assertEqual(False, node.exp_block_pairs[1][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[1][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[1][1].stats[0], parser.StatBreak))
        self.assertIsNone(node.exp_block_pairs[2][0])
        self.assertTrue(isinstance(node.exp_block_pairs[2][1].stats[0], parser.StatReturn))
        self.assertIsNone(node.exp_block_pairs[2][1].stats[0].explist)

    def testStatIfShort(self):
        p = get_parser('if (true) break\nreturn')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(1, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))
        
    def testStatIfShortEOF(self):
        p = get_parser('if (true) break')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(7, p._pos)
        self.assertEqual(1, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))

    def testStatIfShortElse(self):
        p = get_parser('if (true) break else break\nreturn')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(11, p._pos)
        self.assertEqual(2, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))
        self.assertIsNone(node.exp_block_pairs[1][0])
        self.assertEqual(1, len(node.exp_block_pairs[1][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[1][1].stats[0], parser.StatBreak))

    def testStatIfShortEmptyElse(self):
        p = get_parser('if (true) break else  \nreturn')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertEqual(1, len(node.exp_block_pairs))
        self.assertEqual(True, node.exp_block_pairs[0][0].value)
        self.assertEqual(1, len(node.exp_block_pairs[0][1].stats))
        self.assertTrue(isinstance(node.exp_block_pairs[0][1].stats[0], parser.StatBreak))

    def testStatFor(self):
        p = get_parser('for foo=1,3 do break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(13, p._pos)
        self.assertEqual('foo', node.name.value)
        self.assertTrue(node.exp_init.value.matches(lexer.TokNumber('1')))
        self.assertTrue(node.exp_end.value.matches(lexer.TokNumber('3')))
        self.assertIsNone(node.exp_step)
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))

    def testStatForStep(self):
        p = get_parser('for foo=1,3,10 do break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(15, p._pos)
        self.assertEqual('foo', node.name.value)
        self.assertTrue(node.exp_init.value.matches(lexer.TokNumber('1')))
        self.assertTrue(node.exp_end.value.matches(lexer.TokNumber('3')))
        self.assertTrue(node.exp_step.value.matches(lexer.TokNumber('10')))
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))

    def testStatForIn(self):
        p = get_parser('for foo, bar in 1, 3 do\n  break\nend\n')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(20, p._pos)
        self.assertEqual(2, len(node.namelist.names))
        self.assertEqual('foo', node.namelist.names[0].value)
        self.assertEqual('bar', node.namelist.names[1].value)
        self.assertEqual(2, len(node.explist.exps))
        self.assertTrue(node.explist.exps[0].value.matches(lexer.TokNumber('1')))
        self.assertTrue(node.explist.exps[1].value.matches(lexer.TokNumber('3')))
        self.assertEqual(1, len(node.block.stats))
        self.assertTrue(isinstance(node.block.stats[0], parser.StatBreak))
        
    def testStatFunction(self):
        p = get_parser('function foo(a, b, c) break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(16, p._pos)
        self.assertEqual(1, len(node.funcname.namepath))
        self.assertEqual('foo', node.funcname.namepath[0].value)
        self.assertIsNone(node.funcname.methodname)
        self.assertEqual(3, len(node.funcbody.parlist.names))
        self.assertEqual('a', node.funcbody.parlist.names[0].value)
        self.assertEqual('b', node.funcbody.parlist.names[1].value)
        self.assertEqual('c', node.funcbody.parlist.names[2].value)
        self.assertIsNone(node.funcbody.dots)
        self.assertEqual(1, len(node.funcbody.block.stats))
        self.assertTrue(isinstance(node.funcbody.block.stats[0], parser.StatBreak))
        
    def testStatLocalFunction(self):
        p = get_parser('local function foo(a, b, c) break end')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(18, p._pos)
        self.assertEqual('foo', node.funcname.value)
        self.assertEqual(3, len(node.funcbody.parlist.names))
        self.assertEqual('a', node.funcbody.parlist.names[0].value)
        self.assertEqual('b', node.funcbody.parlist.names[1].value)
        self.assertEqual('c', node.funcbody.parlist.names[2].value)
        self.assertIsNone(node.funcbody.dots)
        self.assertEqual(1, len(node.funcbody.block.stats))
        self.assertTrue(isinstance(node.funcbody.block.stats[0], parser.StatBreak))
        
    def testStatLocalAssignment(self):
        p = get_parser('local foo, bar, baz')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(9, p._pos)
        self.assertEqual(3, len(node.namelist.names))
        self.assertEqual('foo', node.namelist.names[0].value)
        self.assertEqual('bar', node.namelist.names[1].value)
        self.assertEqual('baz', node.namelist.names[2].value)
        self.assertIsNone(node.explist)
        
    def testStatLocalAssignmentWithValues(self):
        p = get_parser('local foo, bar, baz = 1, 2, 3')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(19, p._pos)
        self.assertEqual(3, len(node.namelist.names))
        self.assertEqual('foo', node.namelist.names[0].value)
        self.assertEqual('bar', node.namelist.names[1].value)
        self.assertEqual('baz', node.namelist.names[2].value)
        self.assertEqual(3, len(node.explist.exps))
        self.assertTrue(node.explist.exps[0].value.matches(lexer.TokNumber('1')))
        self.assertTrue(node.explist.exps[1].value.matches(lexer.TokNumber('2')))
        self.assertTrue(node.explist.exps[2].value.matches(lexer.TokNumber('3')))

    def testStatGoto(self):
        p = get_parser('goto foobar')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(3, p._pos)
        self.assertEqual('foobar', node.label)

    def testStatLabel(self):
        p = get_parser('::foobar::')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(1, p._pos)
        self.assertEqual('foobar', node.label)

    def testStatAssignmentAnonymousFunctionTable(self):
        p = get_parser('''
player =
{
    init=function(this)
        print(t1)
    end,
    update=function(this)
        print(t2)
    end,
    draw=function(this)
        print(t3)
    end
}
''')
        node = p._stat()
        self.assertIsNotNone(node)
        self.assertEqual(61, p._pos)
        self.assertEqual(1, len(node.varlist.vars))
        self.assertEqual('player', node.varlist.vars[0].name.value)
        self.assertTrue(node.assignop.matches(lexer.TokSymbol('=')))
        self.assertEqual(1, len(node.explist.exps))
        self.assertEqual(3, len(node.explist.exps[0].value.fields))
        self.assertEqual('init', node.explist.exps[0].value.fields[0].key_name.value)
        self.assertTrue(isinstance(node.explist.exps[0].value.fields[0].exp.value, parser.Function))
        self.assertEqual('update', node.explist.exps[0].value.fields[1].key_name.value)
        self.assertTrue(isinstance(node.explist.exps[0].value.fields[1].exp.value, parser.Function))
        self.assertEqual('draw', node.explist.exps[0].value.fields[2].key_name.value)
        self.assertTrue(isinstance(node.explist.exps[0].value.fields[2].exp.value, parser.Function))
        
    def testChunk(self):
        p = get_parser(LUA_SAMPLE)
        node = p._chunk()
        self.assertIsNotNone(node)
        self.assertEqual(628, p._pos)
        self.assertEqual(14, len(node.stats))

    def testChunkExtraSemis(self):
        p = get_parser(' ; ; foo=1; bar=1; ;\n;baz=3; \n;  ;')
        node = p._chunk()
        self.assertIsNotNone(node)
        self.assertEqual(27, p._pos)
        self.assertEqual(3, len(node.stats))

    def testProcessTokens(self):
        tokens = get_tokens(LUA_SAMPLE)
        p = parser.Parser(version=4)
        p.process_tokens(tokens)
        self.assertIsNotNone(p.root)
        self.assertEqual(14, len(p.root.stats))
        

if __name__ == '__main__':
    unittest.main()
