import unittest
from analytics.forecast import daily_average, estimated_unsold

class ForecastTests(unittest.TestCase):
    def test_average(self):
        self.assertEqual(daily_average([10,12,8,15,20,25,15],7),15.0)
    def test_unsold(self):
        self.assertEqual(estimated_unsold(50,15,3),5)
    def test_expired(self):
        self.assertEqual(estimated_unsold(10,3,-1),10)
    def test_bad_input(self):
        with self.assertRaises(ValueError):
            daily_average([1],0)

if __name__=='__main__':
    unittest.main()
