"""测试 Decimal 类型比较"""
from decimal import Decimal

print('Testing Decimal comparison:')
print('14.45 == Decimal("14.450000"):', 14.45 == Decimal('14.450000'))
print('float(14.45) == float(Decimal("14.450000")):', float(14.45) == float(Decimal('14.450000')))
print('abs(float(14.45) - float(Decimal("14.450000"))):', abs(float(14.45) - float(Decimal('14.450000'))))

print('\nTesting with tolerance:')
tolerance = 1e-6
diff = abs(float(14.45) - float(Decimal('14.450000')))
print(f'diff: {diff}')
print(f'diff <= tolerance: {diff <= tolerance}')

print('\nTesting other values:')
print('2.35 == Decimal("2.35000000"):', 2.35 == Decimal('2.35000000'))
print('float(2.35) == float(Decimal("2.35000000")):', float(2.35) == float(Decimal('2.35000000')))
print('abs(float(2.35) - float(Decimal("2.35000000"))):', abs(float(2.35) - float(Decimal('2.35000000'))))
