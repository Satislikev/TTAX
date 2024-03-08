import argparse
import csv
import requests
import logging
from io import StringIO
from tabulate import tabulate
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TTAX")

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("document", type=str, help="Path to the stock document")
    parser.add_argument("year", type=int, help="Tax year")
    return parser.parse_args()

def main():
    args = parse_arguments()
    tax_document_path = args.document
    tax_year = args.year

    stock_data = read_stock_document(tax_document_path)
    if not stock_data:
        logger.error("Failed to read stock document.")
        return

    rate_data = get_conversion_rate(tax_year)
    if not rate_data:
        logger.error("Failed to fetch conversion rates.")
        return

    detailed_table_data = calculate_proceeds_costs(stock_data, rate_data)
    headers = ["Closed Date", "Quantity", "Proceed SEK rate", "Converted proceed", "Cost SEK Rate", "Converted cost", "Loss/Gain"]
    print_tabulated_data(detailed_table_data, headers)
    headers = [ "Total quantity", "Total proceed", "Total cost", "Loss/Gain"]
    print_tabulated_data(summary_data(detailed_table_data), headers)

def read_stock_document(filename):
    stock_data = []
    with open(filename, 'r') as file:
        reader = csv.reader(file)
        next(reader)
        headers = next(reader)
        headers = [header.strip().lower() for header in headers]
        # Find index of 'closed date' column
        closed_date_index = headers.index('closed date')
        opened_date_index = headers.index('opened date')
        
        for row in reader:
            closed_date = convert_date(row[closed_date_index])
            opened_date = convert_date(row[opened_date_index])
            proceeds_per_share = row[headers.index('proceeds per share')].replace('$', '')
            cost_per_share = row[headers.index('cost per share')].replace('$', '')
            quantity = row[headers.index('quantity')]
            
            stock_data.append([closed_date, proceeds_per_share, opened_date, cost_per_share, quantity])
    
    return stock_data

def convert_date(date):
    if date:
        parts = date.split('/')
        if len(parts) == 3:
            return '-'.join([parts[2], parts[0], parts[1]])
    return ''

def get_conversion_rate(tax_year):
    year_before = tax_year - 1 
    from_date = f"{year_before}-01-01"
    to_date = f"{tax_year}-12-31"
    url = f"https://www.riksbank.se/sv/statistik/rantor-och-valutakurser/sok-rantor-och-valutakurser/?a=D&from={from_date}&fs=3&s=g130-SEKUSDPMI&to={to_date}&d=Dot&export=csv"
    
    response = requests.get(url)
    
    if response.status_code == 200:
        csv_data = {}
        csv_reader = csv.reader(StringIO(response.text), delimiter=";")
        
        for row in csv_reader:
            csv_data[row[0]] = row[3]
        
        return csv_data
    else:
        logger.error(f"Failed to fetch conversion data. Status code: {response.status_code}")
        return None

def calculate_proceeds_costs(stock_data, rate_data):
    detailed_table_data = []
    
    for transaction in stock_data:
        proceed_rate = float(rate_data[transaction[0]])
        cost_rate = float(rate_data[transaction[2]])
        converted_proceeds =  (float(transaction[1]) * int(transaction[4])) * float(proceed_rate)
        converted_cost =  (float(transaction[3]) * int(transaction[4])) * float(cost_rate)
        detailed_table_data.append([transaction[0], int(transaction[4]), proceed_rate, round(converted_proceeds,2), cost_rate, round(converted_cost,2), round(converted_proceeds - converted_cost, 2)])
    
    return detailed_table_data

def print_tabulated_data(data, headers):
    
    print(tabulate(data, headers=headers, tablefmt="pretty"))

def summary_data(table_data):
    result_list= []
    # Convert the table data into a pandas DataFrame
    columns = ["Closed Date", "Quantity", "Proceed rate", "Converted proceed", "Cost Rate", "Converted cost", "Loss/Gain"]
    df = pd.DataFrame(table_data, columns=columns)

    df.drop(['Proceed rate', 'Cost Rate'], axis=1, inplace=True)
    
    sum_quantity = df['Quantity'].sum()
    sum_converted_proceed = df['Converted proceed'].sum()
    sum_converted_cost = df['Converted cost'].sum()
    sum_loss_gain = df['Loss/Gain'].sum()

    result_list.append([sum_quantity, round(sum_converted_proceed, 2), round(sum_converted_cost, 2), round(sum_loss_gain, 2)])
    return result_list


if __name__ == "__main__":
    main()