
import unittest
from unittest.mock import patch, MagicMock
from absl import flags
from absl.testing import flagsaver
import sdmx_cli

FLAGS = flags.FLAGS


class SdmxCliTest(unittest.TestCase):

    def setUp(self):
        # Ensure flags are parsed for testing
        FLAGS(['test_program'])

    @patch('sdmx_cli.SdmxClient')
    def test_handle_download_metadata(self, mock_client_class):
        mock_client = mock_client_class.return_value
        
        with flagsaver.flagsaver(
                endpoint='http://example.org',
                agency='AG1',
                dataflow='DF1',
                version='1.0',
                output_path='meta.xml'):
            sdmx_cli.handle_download_metadata()
            
        mock_client_class.assert_called_with('http://example.org', 'AG1')
        mock_client.download_metadata.assert_called_with(
            'DF1', 'meta.xml', version='1.0')

    @patch('sdmx_cli.SdmxClient')
    def test_handle_download_data(self, mock_client_class):
        mock_client = mock_client_class.return_value
        
        # Mock the dataflow response structure for DSD extraction
        mock_flow_msg = MagicMock()
        mock_dsd = MagicMock()
        mock_flow_msg.dataflow.__getitem__.return_value.structure = mock_dsd
        mock_client.client.dataflow.return_value = mock_flow_msg

        with flagsaver.flagsaver(
                endpoint='http://example.org',
                agency='AG1',
                dataflow='DF1',
                version='1.0',
                key=['K1:V1'],
                param=['P1:V2'],
                output_path='data.csv'):
            sdmx_cli.handle_download_data()
            
        mock_client_class.assert_called_with('http://example.org', 'AG1')
        
        # Verify download_data_as_csv is called with version
        mock_client.download_data_as_csv.assert_called_with(
            'DF1', 
            {'K1': 'V1'}, 
            {'P1': 'V2'}, 
            'data.csv',
            version='1.0')

    def test_parse_key_value_pairs(self):
        self.assertEqual(sdmx_cli.parse_key_value_pairs(['a:1', 'b:2']), {'a': '1', 'b': '2'})
        self.assertEqual(sdmx_cli.parse_key_value_pairs([]), {})
        with self.assertRaises(ValueError):
            sdmx_cli.parse_key_value_pairs(['invalid'])


if __name__ == '__main__':
    unittest.main()
