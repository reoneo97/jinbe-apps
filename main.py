import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io
if 'output' not in st.session_state:
    st.session_state['output'] = None
    st.session_state["output2"] = None


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
        st.error(f'Found issue with processing {title}')
        return date_range, 'No Store Number!'

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

def process_excel_file_label_inputs(files):
    dfs = []
    
    for file in files:

        df = pd.read_excel(file)
        title = df.columns[0]

        date = title.split("_")[1].split(" ")[0]
        store_no = title.split(":")[-1].split('(')[-1].split(')')[0]

        df = pd.read_excel(file, header=3)
        df['Date'] = date
        df['Store No'] = store_no
        dfs.append(df)
    all_df = pd.concat(dfs)
    return all_df

def main():
    # st.image('./images.jpeg')
    tabs = st.tabs(['Data Extract Reports', 'Label Model Inputs'])
    with tabs[0]:
        st.markdown('## Data Extract Reports')
        st.markdown('This page contains some tools for data processing')

        excel_files = st.file_uploader('Upload Excel Files Here:', accept_multiple_files=True)
        run = st.button('Run Script 🐳')
        if run:
            if excel_files:
                with st.spinner('Running'):
                    all_data = []
                    for file in excel_files:
                        try:
                            df = process_excel_file(file)
                            all_data.append(df)
                        except:
                            st.error(f'Issues Processing {file}')
                    all_df = pd.concat(all_data)
                    st.session_state['output'] = all_df
            else:
                st.error('No Files have been uploaded')
        if st.session_state['output'] is not None:
            output_csv = st.session_state['output'].to_csv()
            st.markdown('Preview')
            st.dataframe(st.session_state['output'])
            fn = get_time()  +"_korea_agg.csv"

    with tabs[1]:
        st.markdown('## Label Model Inputs')
        st.markdown('This page contains tools to concatenate files and append the store # and date behind')
        excel_files = st.file_uploader(
            "Upload Excel Files Here:", accept_multiple_files=True,
            key='label_files'
        )
        run = st.button('Run Script 🐳',key='run2')
        if run:
            if excel_files:
                with st.spinner('Running'):

                    output = process_excel_file_label_inputs(excel_files)
                    st.session_state['output2'] = output
            else:
                st.error('No Files have been uploaded')
        if st.session_state['output2'] is not None:
            # output_csv = st.session_state['output'].to_csv()
            st.markdown('Row Count Preview')
            output_df = st.session_state['output2']
            st.dataframe(
                output_df.groupby(["Store No", "Date"]).count()["Unnamed: 0"].unstack()
            )
            st.dataframe(output_df)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                output_df.to_excel(writer,index=False)
                writer.save()

                st.download_button(
                    label='Download Result',
                    data=buffer,
                    file_name=get_time()  +"_korea_label_file.xlsx",
                    mime="application/vnd.ms-excel"
                )

if __name__ == "__main__":
    main()
