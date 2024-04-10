import streamlit as st
import pandas as pd
import re
from datetime import datetime

if 'output' not in st.session_state:
    st.session_state['output'] = None



st.set_page_config(
    page_title='Jinbesan Reports', page_icon="🐳", layout="centered")
def get_time():
    return datetime.now().strftime('%Y-%m-%d %H-%M')

def extract_info_from_title(title):
    pattern = r'\d{4}-\d{2}-\d{2}'
    dates = re.findall(pattern, title)
    assert len(dates) == 2, f'There are more than 2 Dates found in the Title of the Excel File. Found {dates}'
    sd, ed = dates
    date_range = pd.date_range(sd, ed)
    store_no_pattern = r'\(\d{8}\)'
    store_no = re.search(store_no_pattern, title)
    if not store_no:
        print('NO STORE NUMBER FOUND')
    store_no = int(store_no.group()[1:-1])
    return date_range, store_no

def process_excel_file(file):
    df = pd.read_excel(file)
    title = df.columns[0]
    df = pd.read_excel(file,header=[2,3])
    df.columns = [i[0] +"-"+ i[1] for i in df.columns]
    df.columns = ['Index#','Menu Code', 'Menu Name', 'Size'] + list(df.columns[4:])
    df = df.iloc[:-1]
    # Sales ,Units ,Price Per Unit

    date_range, store_no = extract_info_from_title(title)

    item_names = df.iloc[:,:4]
    slcs = []
    for i, date in enumerate(date_range):
        col_s = i*3 + 7
        slc = pd.concat([item_names.copy(), df.iloc[:,col_s:col_s+3]], axis=1)
        slc.columns = list(slc.columns[:-3]) + ['Sales','Units','Price Per Unit']
        slc['Store Number'] = store_no
        slc['Date'] = date
        slc = slc[["Store Number",'Date'] + list(slc.columns[:-2])]
        slcs.append(slc)
    convert_df = pd.concat(slcs)
    return convert_df


def main():
    # st.image('./images.jpeg')
    st.markdown('## Data Extract Reports')
    st.markdown('This page contains some tools for data processing')

    excel_files = st.file_uploader('Upload Excel Files Here:', accept_multiple_files=True)
    run = st.button('Run Script 🐳')
    if run:
        if excel_files:
            with st.spinner('Running'):
                all_data = []
                for file in excel_files:
                    df = process_excel_file(file)
                    all_data.append(df)
                all_df = pd.concat(all_data)
                st.session_state['output'] = all_df
        else:
            st.error('No Files have been uploaded')
    if st.session_state['output'] is not None:
        output_csv = st.session_state['output'].to_csv()
        st.markdown('Preview')
        st.dataframe(st.session_state['output'])
        fn = get_time()  +"_korea_agg.csv"
        # st.download_button(
        #     'Download Output',
        #     data=output_csv,
        #     file_name=fn,
        #     mime='text/csv'
        # )


if __name__ == "__main__":
    main()