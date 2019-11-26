# ==== IMPORTS ===========================================================
# ------------------------------------------------------------------------
import streamlit as st
import stlide as stl
# ------------------------------------------------------------------------
# ========================================================================


# ==== TEMPLATE ==========================================================
# ------------------------------------------------------------------------
stl.initialize()
# ------------------------------------------------------------------------
# ========================================================================


# ==== PAGES =============================================================
# ------------------------------------------------------------------------
@stl.slide
def first():
    st.markdown('# Hello')

@stl.slide
def second():
    st.markdown('# World')

@stl.slide
def third():
    st.markdown('# !')

@stl.slide
def another():
    st.markdown('# :-)')

@stl.slide
def another_one():
    name = st.sidebar.text_input('Name', 'Stranger')
    st.markdown(f'# Nice to meet you {name}!')

@stl.slide
def with_image():
    st.image('./graphics/image.jpg', 'This is an image!', use_column_width=True)

@stl.slide
def with_code():
    code = '''def f():
    print('Hello World!')'''
    st.code(code, language='python')

@stl.slide
def with_code_that_runs():
    try:
        sample_code = '''def f():
    return 'Hi!'
'''
        code = st.text_area('Insert your code:', value=sample_code)
        expression = st.text_area('Test here:', value='f()')

        st.write('**Code**')
        st.code(code, language='python')

        exec(code)
        st.write('**Result**     \n >', eval(expression))

    except SyntaxError as error:
        st.write('**Error!**')
        st.write(error)

# ------------------------------------------------------------------------
#=========================================================================


# # === RENDER =============================================================
# # ------------------------------------------------------------------------
stl.render()
# # ------------------------------------------------------------------------
# #=========================================================================
