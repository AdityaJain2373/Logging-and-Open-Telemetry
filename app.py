import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import SpanKind
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
import logging


app = Flask(__name__)
logging.getLogger('werkzeug').disabled=True
app.secret_key = 'secret'
COURSE_FILE = 'course_catalog.json'


excluded_urls = ["GET /favicon.ico"]
excluded_urls_string = ",".join(excluded_urls)
FlaskInstrumentor().instrument_app(app, excluded_urls = excluded_urls_string)

resource = Resource(attributes = {
    "service.name" : "course_management_service"
})

trace.set_tracer_provider(TracerProvider(resource = resource))
console_exporter = ConsoleSpanExporter()
span_processor = BatchSpanProcessor(console_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)


tracer = trace.get_tracer(__name__)
logging.basicConfig(level = logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S', handlers = [logging.FileHandler("app.log")])
logger = logging.getLogger(__name__)



def load_courses():
    if not os.path.exists(COURSE_FILE):    
        return [] 
    with open(COURSE_FILE, 'r') as file:
        return json.load(file)


def save_courses(data):

    courses = load_courses()  
    courses.append(data)  
    with open(COURSE_FILE, 'w') as file:
        json.dump(courses, file, indent=4)


@app.route('/')
def index():
    with tracer.start_as_current_span("Index page") as span:
        span.set_attribute("operation", "render index")
        span.set_attribute("request.method", request.method)
        span.set_attribute("user.ip", request.remote_addr)
        return render_template('index.html')

@app.route('/catalog')
def course_catalog():
    with tracer.start_as_current_span("Course catalog") as span:
        span.set_attribute("operations", "render_course_catalog")
        courses = load_courses()
        span.set_attribute("num_courses", len(courses))
        return render_template('course_catalog.html', courses=courses)


@app.route('/course/<code>')
def course_details(code):
    with tracer.start_as_current_span("Course details page") as span:
        span.set_attribute("operations", "render_course_details")
        span.set_attribute("request.method", request.method)
        span.set_attribute("user.ip", request.remote_addr)
        span.set_attribute("course.code", code)
        courses = load_courses()
        course = next((course for course in courses if course['code'] == code), None)
        if not course:
            flash(f"No course found with code '{code}'.", "error")
            return redirect(url_for('course_catalog'))
        span.set_attribute("course.name", course['name'])
        logger.info(f"Course details page of course {code} has been accessed.")
        return render_template('course_details.html', course=course)


@app.route('/add_course', methods = ["GET","POST"])
def add_course():
    if request.method == "POST":
        with tracer.start_as_current_span("AddCourse") as span:
            span.set_attribute("operation", "add_course")
            span.set_attribute("request.method", request.method)
            span.set_attribute("user.ip", request.remote_addr)

            course_code = request.form.get('code')
            course_name = request.form.get('name')
            instructor = request.form.get('instructor')
            semester = request.form.get('semester')
            schedule = request.form.get('schedule')
            classroom = request.form.get('classroom')
            prerequisites = request.form.get('prerequisites')
            grading = request.form.get('grading')
            description = request.form.get('description')

            if not course_code or not course_name :
                logger.error("Missing required fields: course_code or course_name.")
                flash("Course code and name are required.", "error")
                span.set_attribute("status", "failed")
                return render_template('add_course.html')

            new_course = {
                'code': course_code,
                'name': course_name,
                'instructor': instructor,
                'semester': semester,
                'schedule': schedule,
                'classroom': classroom,
                'prerequisites': prerequisites,
                'grading': grading,
                'description': description
            }

            courses = load_courses()
            for course in courses:
                if course['code'] == new_course['code']:
                    span.set_attribute("status", "failed")
                    return render_template('add_course.html', message="Course code already exists.")
            
            save_courses(new_course)

            flash(f"Course with code {course_code} has been added.", "Success")
            logger.info(f"course {course_name} with course code {course_code} added successfully.")
            span.set_attribute("status", "success")
            span.set_attribute("course.name", course_name)
            span.set_attribute("course.code", course_code)
        return redirect(url_for('course_catalog'))
    
    return render_template('add_course.html')


@app.route('/delete_course/<code>', methods = ["GET", "POST"])
def delete_course(code):
    with tracer.start_as_current_span("DeleteCourse") as span:
        span.set_attribute("operation", "delete_course")
        span.set_attribute("request.method", request.method)
        span.set_attribute("user.ip", request.remote_addr)
        span.set_attribute("course.code", code)

        courses = load_courses()
        updated_courses = [course for course in courses if course['code'] != code]

        with open(COURSE_FILE, 'w') as file:
            json.dump(updated_courses, file, indent=4)

        flash(f"Course with code {code} has been deleted.", "success")
        logger.info(f"Course with code {code} has been deleted successfully.")
        span.set_attribute("status", "success")
        span.set_attribute("course.code", code)
    return redirect(url_for('course_catalog'))


if __name__ == '__main__':
    open('app.log','w').write('')
    logger.info("go to local host {http://127.0.0.1:5000}")
    app.run(debug=True)
