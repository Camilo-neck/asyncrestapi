import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from .utils import formatDate
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

class SiaScraperException(Exception):
    class SessionNotSet(Exception):
        def __init__(self) -> None:
            super().__init__("Must set session by createSession() or loadSession(sessionData)")

    class CareerNotSet(Exception):
        def __init__(self) -> None:
            super().__init__("Must set career by setCareer(careerCode)")

class SiaScraper():
    def __init__(self, domain="sia.unal.edu.co"):
        self.domain = domain
        self.url = f"https://{self.domain}/Catalogo/facespublico/public/servicioPublico.jsf"
        self.careerName = "N/A"
        self.careerCode = ''
        self.courseList = []
        self.session = None

        self.isElectives = False

        self.adf_ads_page_id = '1'  # Parece que no afecta
        self.headers = {
            'authority': f'{self.domain}',
            'accept': '*/*',
            'accept-language': 'es-419,es;q=0.9,en;q=0.8',
            'adf-ads-page-id': self.adf_ads_page_id,
            'adf-rich-message': 'true',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': f'https://{self.domain}',
            'referer': self.url,
            'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        }

        self.dropdowns = ['pt1:r1:0:soc1::content', 'pt1:r1:0:soc9::content',
                          'pt1:r1:0:soc2::content', 'pt1:r1:0:soc3::content']

    ##################### DECORATORS #####################

    def check_session(func):
        def wrapper(self, *args, **kwargs):
            # if not self.validSession():
            if self.session == None:
                raise SiaScraperException.SessionNotSet from SiaScraperException
            return func(self, *args, **kwargs)
        return wrapper

    def check_career(func):
        def wrapper(self, *args, **kwargs):
            if self.careerCode == '':
                raise SiaScraperException.CareerNotSet from SiaScraperException
            return func(self, *args, **kwargs)
        return wrapper

    ##################### PUBLIC METHODS #####################

    def validSession(self):  # Forma cutre de ver si la sesion ya expiro
        if self.session == None or "AdfPage.PAGE.__getSessionTimeoutHelper().__alertTimeout()" in self.postRequest(data={}).text:
            return False
        return True

    def createSession(self):
        self.session = requests.Session()
        r = self.session.get(
            f"https://{self.domain}/Catalogo/facespublico/public/servicioPublico.jsf?taskflowId=task-flow-AC_CatalogoAsignaturas")
        self.mainPageHtml = r.content

        soup = BeautifulSoup(r.content, "html.parser")
        # print(r.content)

        self.javax_faces_ViewState = soup.find(
            "input", {"type": "hidden", "name": "javax.faces.ViewState"})['value']
        self.Adf_Window_Id = soup.find(
            "input", {"type": "hidden", "name": "Adf-Window-Id"})['value']

        # self.Adf_Page_Id = soup.find("input", {"type": "hidden", "name":"Adf-Page-Id"})['value']

        self.Adf_Page_Id = '0'  # Parece que no afecta [0,1,2]

        self.params = {
            'Adf-Window-Id': self.Adf_Window_Id,
            'Adf-Page-Id': self.Adf_Page_Id,
        }

        return self

    @check_session
    def getSessionData(self):
        return {
            "session_headers": dict(self.session.headers),
            "session_cookies": self.session.cookies.get_dict(),
            "params": self.params,
            "javax_faces_ViewState": self.javax_faces_ViewState,
            "careerCode": self.careerCode,
            "careerName": self.careerName,
            "isElectives": self.isElectives
        }

    def loadSession(self, sessionData):
        self.session = requests.session()

        self.session.headers = sessionData["session_headers"]
        self.session.cookies.update(sessionData["session_cookies"])

        self.params = sessionData["params"]
        self.Adf_Page_Id = self.params["Adf-Page-Id"]
        self.Adf_Window_Id = self.params["Adf-Window-Id"]

        self.javax_faces_ViewState = sessionData["javax_faces_ViewState"]

        self.careerCode = sessionData["careerCode"]
        self.careerName = sessionData["careerName"]
        self.careerIndexs = self.careerCode.split("-")

        self.isElectives = sessionData["isElectives"]

        r = self.session.get(
            f"https://{self.domain}/Catalogo/facespublico/public/servicioPublico.jsf?taskflowId=task-flow-AC_CatalogoAsignaturas")
        html = r.content
        self.courseList = self.getCourseList(html, 'html.parser')

        return self

    @check_session
    def setCareer(self, searchCode, electives=False):
        # if not self.validSession(): raise

        self.careerCode = searchCode
        self.careerIndexs = searchCode.split("-")

        dPlan = self.getRequestData("dPlan")
        dSede = self.getRequestData("dSede")
        dFacultad = self.getRequestData("dFacultad")
        dCarrera = self.getRequestData("dCarrera")
        dTipologia = self.getRequestData(
            "dTipologia", tiplogyIndex='7' if electives else '')  # dropdown tipologia

        dataList = [dPlan, dSede, dFacultad, dCarrera, dTipologia]

        if not electives:
            dMostrar = self.getRequestData("dMostrar", self.careerIndexs)
            dataList.append(dMostrar)

        else:
            dFP = self.getRequestData("dFP")
            dS = self.getRequestData("dS")
            dMostrarE = self.getRequestData("dMostrarE")

            dataList.append(dFP)
            dataList.append(dS)
            dataList.append(dMostrarE)

        self.update_view_state()

        for data in dataList:
            response = self.postRequest(data=data)

        xml = response.text

        self.careerName = self.getcareerName()

        self.courseList = self.getCourseList(xml, 'lxml')
        self.isElectives = electives

        return self

    @check_session
    @check_career
    def getCourseInfo(self, courseIndex=0, cCode=''):
        courseIndex = self.__getCourseIndex(cCode) if cCode != '' else courseIndex
        xml = self.__getCourseXml(courseIndex)
        return self.__scrapeInfo(xml)

    @check_session
    @check_career
    def getCoursePrereqs(self, courseIndex=0, cCode=''):
        courseIndex = self.__getCourseIndex(cCode) if cCode != '' else courseIndex
        xml = self.__getCourseXml(courseIndex)
        return self.__scrapePrereqs(xml)

    @check_session
    @check_career
    def scrapeCourses(self, coursesIndexs=[], coursesCodes=[]):
        coursesIndexs = [self.__getCourseIndex(
            cCode) for cCode in coursesCodes] if coursesCodes != [] else coursesIndexs
        coursesIndexs.sort()
        courses = [self.getCourseInfo(courseIndex) for courseIndex in coursesIndexs]
        for i in range(len(courses)):
            courses[i]["codigo"] = coursesCodes[i]

        return courses

    @check_session
    def update_view_state(self):
        r = self.session.get(self.url, params=self.params)
        view_state_regex = re.compile(
            b'<input type="hidden" name="javax.faces.ViewState" value="(.*?)">')
        view_state = view_state_regex.search(r.content).group(1)
        self.javax_faces_ViewState = view_state.decode('utf-8')

    @check_session
    def postRequest(self, data):
        return self.session.post(self.url, params=self.params, headers=self.headers, data=data)

    @check_session
    #@check_career
    def getCourseList(self, html, parser):

        soup = BeautifulSoup(html, parser)
        rows = soup.find_all("tr", {"class": "af_table_data-row"})
        courseList = []
        for row in rows:
            data = row.find_all("span", {"class": "af_column_data-container"})
            courseCode = data[0].getText()
            courseName = data[1].getText()
            courseList .append({
                courseCode: courseName
            })
        return courseList

    @check_session
    @check_career
    def getcareerName(self):  # Esto no da el nombre completo, el nombre completo esta en las opciones de los dropdowns (encima es una solucion cutre)
        soup = BeautifulSoup(self.__getCourseXml(1), 'lxml')
        return soup.find_all("span", {"class": "row detass-plan af_panelGroupLayout"})[0].text

    def getRequestData(self, dataName, careerIndexs=[], tiplogyIndex=0):
        if careerIndexs == []:
            careerIndexs = self.careerIndexs

        if dataName == "dPlan":
            return f'pt1:r1:0:soc1={careerIndexs[0]}&pt1:r1:0:soc9=0&pt1:r1:0:soc2=&pt1:r1:0:soc5=&pt1:r1:0:soc10=0&pt1:r1:0:it10=&pt1:r1:0:it11=&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id={self.Adf_Window_Id}&Adf-Page-Id={self.Adf_Page_Id}&javax.faces.ViewState={self.javax_faces_ViewState}&event=pt1%3Ar1%3A0%3Asoc1&event.pt1:r1:0:soc1=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22autoSubmit%22%3E%3Cb%3E1%3C%2Fb%3E%3C%2Fk%3E%3Ck+v%3D%22suppressMessageShow%22%3E%3Cs%3Etrue%3C%2Fs%3E%3C%2Fk%3E%3Ck+v%3D%22type%22%3E%3Cs%3EvalueChange%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%3A0%3Asoc1'

        elif dataName == "dSede":
            return f'pt1:r1:0:soc1={careerIndexs[0]}&pt1:r1:0:soc9={careerIndexs[1]}&pt1:r1:0:soc2=&pt1:r1:0:soc5=&pt1:r1:0:soc10=0&pt1:r1:0:it10=&pt1:r1:0:it11=&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id={self.Adf_Window_Id}&Adf-Page-Id={self.Adf_Page_Id}&javax.faces.ViewState={self.javax_faces_ViewState}&event=pt1%3Ar1%3A0%3Asoc9&event.pt1:r1:0:soc9=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22autoSubmit%22%3E%3Cb%3E1%3C%2Fb%3E%3C%2Fk%3E%3Ck+v%3D%22suppressMessageShow%22%3E%3Cs%3Etrue%3C%2Fs%3E%3C%2Fk%3E%3Ck+v%3D%22type%22%3E%3Cs%3EvalueChange%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%3A0%3Asoc9'

        elif dataName == "dFacultad":
            return f'pt1:r1:0:soc1={careerIndexs[0]}&pt1:r1:0:soc9={careerIndexs[1]}&pt1:r1:0:soc2={careerIndexs[2]}&pt1:r1:0:soc5=&pt1:r1:0:soc10=0&pt1:r1:0:it10=&pt1:r1:0:it11=&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id={self.Adf_Window_Id}&Adf-Page-Id={self.Adf_Page_Id}&javax.faces.ViewState={self.javax_faces_ViewState}&event=pt1%3Ar1%3A0%3Asoc2&event.pt1:r1:0:soc2=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22autoSubmit%22%3E%3Cb%3E1%3C%2Fb%3E%3C%2Fk%3E%3Ck+v%3D%22suppressMessageShow%22%3E%3Cs%3Etrue%3C%2Fs%3E%3C%2Fk%3E%3Ck+v%3D%22type%22%3E%3Cs%3EvalueChange%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%3A0%3Asoc2'

        elif dataName == "dCarrera":
            return f'pt1:r1:0:soc1={careerIndexs[0]}&pt1:r1:0:soc9={careerIndexs[1]}&pt1:r1:0:soc2={careerIndexs[2]}&pt1:r1:0:soc3={careerIndexs[3]}&pt1:r1:0:soc5=&pt1:r1:0:soc10=0&pt1:r1:0:it10=&pt1:r1:0:it11=&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id={self.Adf_Window_Id}&Adf-Page-Id={self.Adf_Page_Id}&javax.faces.ViewState={self.javax_faces_ViewState}&event=pt1%3Ar1%3A0%3Asoc3&event.pt1:r1:0:soc3=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22autoSubmit%22%3E%3Cb%3E1%3C%2Fb%3E%3C%2Fk%3E%3Ck+v%3D%22suppressMessageShow%22%3E%3Cs%3Etrue%3C%2Fs%3E%3C%2Fk%3E%3Ck+v%3D%22type%22%3E%3Cs%3EvalueChange%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%3A0%3Asoc3'

        elif dataName == "dTipologia":
            return f'pt1:r1:0:soc1={careerIndexs[0]}&pt1:r1:0:soc9={careerIndexs[1]}&pt1:r1:0:soc2={careerIndexs[2]}&pt1:r1:0:soc5={careerIndexs[3]}&pt1:r1:0:soc4={tiplogyIndex}&pt1:r1:0:soc10=0&pt1:r1:0:it10=&pt1:r1:0:it11=&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id={self.Adf_Window_Id}&Adf-Page-Id={self.Adf_Page_Id}&javax.faces.ViewState={self.javax_faces_ViewState}&event=pt1%3Ar1%3A0%3Asoc4&event.pt1:r1:0:soc4=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22autoSubmit%22%3E%3Cb%3E1%3C%2Fb%3E%3C%2Fk%3E%3Ck+v%3D%22suppressMessageShow%22%3E%3Cs%3Etrue%3C%2Fs%3E%3C%2Fk%3E%3Ck+v%3D%22type%22%3E%3Cs%3EvalueChange%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%3A0%3Asoc4'

        elif dataName == "dMostrar":
            return f'pt1:r1:0:soc1={careerIndexs[0]}&pt1:r1:0:soc9={careerIndexs[1]}&pt1:r1:0:soc2={careerIndexs[2]}&pt1:r1:0:soc3={careerIndexs[3]}&pt1:r1:0:soc4=0&pt1:r1:0:soc5=&pt1:r1:0:soc10=0&pt1:r1:0:it10=&pt1:r1:0:it11=&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id={self.Adf_Window_Id}&Adf-Page-Id={self.Adf_Page_Id}&javax.faces.ViewState={self.javax_faces_ViewState}&event=pt1%3Ar1%3A0%3Acb1&event.pt1:r1:0:cb1=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22type%22%3E%3Cs%3Eaction%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%2Cpt1%3Ar1%3A0%3Acb1'

        ###################

        elif dataName == "dFP":
            return f'pt1:r1:0:soc1={careerIndexs[0]}&pt1:r1:0:soc9={careerIndexs[1]}&pt1:r1:0:soc2={careerIndexs[2]}&pt1:r1:0:soc3={careerIndexs[3]}&pt1:r1:0:soc4=7&pt1:r1:0:soc5=0&pt1:r1:0:soc10=0&pt1:r1:0:it10=&pt1:r1:0:it11=&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id={self.Adf_Window_Id}&Adf-Page-Id={self.Adf_Page_Id}&javax.faces.ViewState={self.javax_faces_ViewState}&oracle.adf.view.rich.DELTAS=%7Bj_id9%3D%7Btitle%3D%7D%2Cj_id8%3D%7B_shown%3D%7D%7D&event=pt1%3Ar1%3A0%3Asoc5&event.pt1:r1:0:soc5=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22autoSubmit%22%3E%3Cb%3E1%3C%2Fb%3E%3C%2Fk%3E%3Ck+v%3D%22suppressMessageShow%22%3E%3Cs%3Etrue%3C%2Fs%3E%3C%2Fk%3E%3Ck+v%3D%22type%22%3E%3Cs%3EvalueChange%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%3A0%3Asoc5'

        elif dataName == "dS":
            return f'pt1:r1:0:soc1={careerIndexs[0]}&pt1:r1:0:soc9={careerIndexs[1]}&pt1:r1:0:soc2={careerIndexs[2]}&pt1:r1:0:soc3={careerIndexs[3]}&pt1:r1:0:soc4=7&pt1:r1:0:soc5=0&pt1:r1:0:soc10=0&pt1:r1:0:soc6={21+int(careerIndexs[1])}&pt1:r1:0:it10=&pt1:r1:0:it11=&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id={self.Adf_Window_Id}&Adf-Page-Id={self.Adf_Page_Id}&javax.faces.ViewState={self.javax_faces_ViewState}&event=pt1%3Ar1%3A0%3Asoc6&event.pt1:r1:0:soc6=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22autoSubmit%22%3E%3Cb%3E1%3C%2Fb%3E%3C%2Fk%3E%3Ck+v%3D%22suppressMessageShow%22%3E%3Cs%3Etrue%3C%2Fs%3E%3C%2Fk%3E%3Ck+v%3D%22type%22%3E%3Cs%3EvalueChange%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%3A0%3Asoc6'

        elif dataName == "dMostrarE":
            return f'pt1:r1:0:soc1={careerIndexs[0]}&pt1:r1:0:soc9={careerIndexs[1]}&pt1:r1:0:soc2={careerIndexs[2]}&pt1:r1:0:soc3={careerIndexs[3]}&pt1:r1:0:soc4=7&pt1:r1:0:soc5=0&pt1:r1:0:soc10=0&pt1:r1:0:soc6={21 + int(careerIndexs[1])}&pt1:r1:0:soc7=&pt1:r1:0:it10=&pt1:r1:0:it11=&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id={self.Adf_Window_Id}&Adf-Page-Id={self.Adf_Page_Id}&javax.faces.ViewState={self.javax_faces_ViewState}&event=pt1%3Ar1%3A0%3Acb1&event.pt1:r1:0:cb1=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22type%22%3E%3Cs%3Eaction%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%2Cpt1%3Ar1%3A0%3Acb1'

    ##################### PRIVATED METHODS #####################

    # Request para seleccionar fila[courseIndex]
    def __selectCourseRow(self, courseIndex):
        data = f'pt1:r1:0:soc1={self.careerIndexs[0]}&pt1:r1:0:soc9={self.careerIndexs[1]}&ppt1:r1:0:soc2={self.careerIndexs[2]}&pt1:r1:0:soc3={self.careerIndexs[3]}&pt1:r1:0:soc4=&pt1:r1:0:soc5=&pt1:r1:0:soc10=0&pt1:r1:0:it10=&pt1:r1:0:it11=&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id={self.Adf_Window_Id}&Adf-Page-Id={self.Adf_Page_Id}&javax.faces.ViewState={self.javax_faces_ViewState}&oracle.adf.view.rich.DELTAS=%7Bpt1%3Ar1%3A0%3At4%3D%7BviewportSize%3D{len(self.courseList)+1}%2Crows%3D{len(self.courseList)}%2CselectedRowKeys%3D{courseIndex}%7D%7D&event=pt1%3Ar1%3A0%3At4&event.pt1:r1:0:t4=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22type%22%3E%3Cs%3Eselection%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%3A0%3At4'
        self.postRequest(data)

    def __getInCourse(self, courseIndex):  # Request para ingresar a materia[courseIndex]
        data = f'pt1:r1:0:soc1={self.careerIndexs[0]}&pt1:r1:0:soc9={self.careerIndexs[1]}&pt1:r1:0:soc2={self.careerIndexs[2]}&pt1:r1:0:soc3={self.careerIndexs[3]}&pt1:r1:0:soc4=&pt1:r1:0:soc5=&pt1:r1:0:soc10=0&pt1:r1:0:it10=&pt1:r1:0:it11=&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id={self.Adf_Window_Id}&Adf-Page-Id={self.Adf_Page_Id}&javax.faces.ViewState={self.javax_faces_ViewState}&oracle.adf.view.rich.RENDER=pt1%3Ar1&event=pt1%3Ar1%3A0%3At4%3A{courseIndex}%3Acl2&event.pt1:r1:0:t4:{courseIndex}:cl2=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22type%22%3E%3Cs%3Eaction%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%2Cpt1%3Ar1%3A0%3At4%3A{courseIndex}%3Acl2'
        return self.postRequest(data)

    def __exitCourse(self):  # Requets para regresar a pagina principal (boton Volver)
        data = f'org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Idl={self.Adf_Window_Id}&Adf-Page-Id=0&javax.faces.ViewState={self.javax_faces_ViewState}&event=pt1%3Ar1%3A1%3Acb4&event.pt1:r1:1:cb4=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22type%22%3E%3Cs%3Eaction%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=pt1%3Ar1%2Cpt1%3Ar1%3A1%3Acb4'
        self.postRequest(data)

    def __getCourseXml(self, courseIndex):
        self.update_view_state()
        self.__selectCourseRow(courseIndex)
        xml = self.__getInCourse(courseIndex).text
        self.__exitCourse()
        self.__selectCourseRow(1)
        # El unico problema es que para pedir la materia de indice 1 no se puede haber pedido primero la materia de indice 0

        return xml

    def __getPlainText(self, xml):
        soup = BeautifulSoup(xml, 'lxml')
        return soup.get_text().split("\xa0\xa0\xa0")[0]

    def __getCourseIndex(self, courseCode):
        for i in range(len(self.courseList)):
            if courseCode in self.courseList[i]:
                return i
        return -1

    def __scrapeInfo(self, xml):
        courseObj = {}
        soup = BeautifulSoup(xml, 'lxml')
        courseName = soup.find_all("h2")[0].text
        credits = soup.find_all(
            "span", class_="row detass-creditos af_panelGroupLayout")[0].text
        groupList = []

        courseObj["nombreAsignatura"] = courseName
        courseObj["cuposDisponibles"] = 0
        courseObj["fechaObtencion"] = formatDate(datetime.now())
        courseObj["grupos"] = groupList
        courseObj["creditos"] = int(credits[credits.index(":")+1:len(credits)])
        courseObj["tipologia"] = soup.find_all(
            "span", class_="detass-tipologia")[0].text.split(": ")[1]

        groups = soup.select(".borde.salto:not(.ficha-docente)")
        # groups = groups[:len(groups)-1]

        for group in groups:
            if (len(group.find_all("div", class_="margin-t")) < 2):
                break

            groupObj = {}
            groupObj["nombreGrupo"] = group.find_all(
                "h2", class_="af_showDetailHeader_title-text0")[0].text
            groupData = list(group.find_all(
                "div", class_="margin-t")[1].children)

            groupObj["profesor"] = groupData[0].text.split(": ")[1]
            groupObj["facultad"] = groupData[1].text.split(": ")[1]
            groupObj["nombre"] = courseName
            shedules = []
            sheduleData = []
            shedule = {}
            sessionData = groupData[2].find_all(
                "span", class_="af_panelGroupLayout")[0]

            if (len(list(sessionData.children)) > 1):
                sessionData = list(list(sessionData.children)[1].children)[4:]

                for s in sessionData:
                    sheduleData = list(s.children)[0].text.split(" ")
                    shedule["dia"] = sheduleData[0]
                    shedule["desde"] = sheduleData[2]
                    shedule["hasta"] = sheduleData[4].replace(".", "")

                    if (len(list(s.children)) > 1):
                        shedule["salon"] = list(s.children)[1].text
                    else:
                        shedule["salon"] = ""
                    shedules.append(shedule)
                    shedule = {}
            groupObj["horarios"] = shedules
            groupObj["duracion"] = groupData[3].text.split(": ")[1]
            groupObj["jornada"] = groupData[4].text.split(": ")[1]
            groupObj["isFavourite"] = False
            if (len(groupData) < 6):
                groupObj["cupos"] = "NaN"
            else:
                groupObj["cupos"] = int(groupData[5].text.split(": ")[1])
                courseObj["cuposDisponibles"] += int(
                    groupData[5].text.split(": ")[1])
            courseObj["grupos"].append(groupObj)
            groupObj = {}

        return courseObj

    def __scrapePrereqs(self, xml):
        soup = BeautifulSoup(xml, 'lxml')
        courseObj = {}
        soup = BeautifulSoup(xml, 'lxml')
        courseName = soup.find_all("h2")[0].text
        credits = soup.find_all(
            "span", class_="row detass-creditos af_panelGroupLayout")[0].text
        courseObj["nombreAsignatura"] = courseName
        courseObj["codigo"] = courseName[courseName.index(
            "(")+1:courseName.index(")")]
        courseObj["creditos"] = int(credits[credits.index(":")+1:len(credits)])
        courseObj["tipologia"] = soup.find_all(
            "span", class_="detass-tipologia")[0].text.split(": ")[1]

        courseObj["condiciones"] = []

        groups = soup.select(".borde.salto:not(.ficha-docente)")
        # groups = groups[:len(groups)-1]

        for group in groups:
            if (len(group.find_all("div", class_="margin-t")) < 2):
                pSection = list(group.select(
                    ".margin-l:not(.af_panelGroupLayout)"))
                pInfo = {}
                pInfo[pSection[0].text] = pSection[0].nextSibling.text
                pInfo[pSection[1].text] = pSection[1].nextSibling.text
                pInfo[pSection[2].text] = pSection[2].nextSibling.text
                pInfo[pSection[3].text] = pSection[3].nextSibling.text
                pInfo["prerrequisitos"] = {}

                for i in range(4, len(pSection)-1, 2):
                    pInfo["prerrequisitos"][pSection[i].text] = pSection[i+1].text

                courseObj["condiciones"].append(pInfo)
                continue

            else:
                continue

        return courseObj

#################

def init_sia_scraper(searchCode, isElectives, sessionData={}):

    if sessionData == {}:
        return create_career_session(searchCode, isElectives)

    print("Loading session...")
    sc = SiaScraper()
    sc.loadSession(sessionData)

    if not sc.validSession():  # No estoy seguro de que esto funcione bien (a veces no sirve)
        print("Ivalid session, creating new one...")
        return create_career_session(searchCode, isElectives)

    if sc.careerCode != searchCode or sc.isElectives != isElectives:
        print("Different career, Setting new career...")
        sc.setCareer(searchCode, electives=isElectives)

    return sc


def create_career_session(searchCode, isElectives):
    sc = SiaScraper()
    print("Creating new session...")
    sc.createSession()
    print("Setting career...")
    sc.setCareer(searchCode, electives=isElectives)
    return sc


if __name__ == "__main__":
    pass
