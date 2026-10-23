"""Versioned Java dispatch exercise and deterministic authored assessment.

The choices are checked against this rubric, not by an LLM or a Java compiler.
Only the store's public projection is suitable for sending to a learner.
"""

LESSON = {
    "id": "java-dynamic-dispatch",
    "title": "Java: method nào thực sự được gọi?",
    "subtitle": "Ba bài ngắn về kế thừa và gọi method bị ghi đè.",
    "concept": "Dynamic dispatch của instance method",
    "version": "1",
}
RUBRIC_VERSION = "1"
CONTENT_VERSION = "2026-10-22.1"

ITEMS = (
    {
        "id": "animal-cat",
        "title": "1. Biến Animal, đối tượng Cat",
        "filename": "Main.java",
        "code": "\n".join((
            "class Animal {",
            '    String speak() { return "animal"; }',
            "}",
            "class Cat extends Animal {",
            "    @Override",
            '    String speak() { return "meow"; }',
            "}",
            "public class Main {",
            "    public static void main(String[] args) {",
            "        Animal pet = new Cat();",
            "        System.out.println(pet.speak());",
            "    }",
            "}",
        )),
        "question": "Đoạn code in ra dòng nào? Hãy chọn trước khi xem gợi ý.",
        "options": (
            {"id": "a", "label": "animal"},
            {"id": "b", "label": "meow"},
            {"id": "c", "label": "Code không biên dịch được"},
        ),
        "correct_option": "b",
        "hints": (
            "Ở dòng 10, kiểu khai báo của biến và lớp của đối tượng được tạo có giống nhau không?",
            "speak() là instance method bị override. Khi chạy, Java chọn implementation theo lớp thực tế của đối tượng.",
        ),
        "explanation": "Kết quả là meow. Dòng 10 tạo một Cat dù biến pet có kiểu Animal. Lệnh pet.speak() ở dòng 11 gọi bản override Cat.speak() ở dòng 6. Bài này chỉ kiểm tra instance method bị override; không áp dụng quy tắc này cho field hay static method.",
        "evidence_lines": (6, 10, 11),
    },
    {
        "id": "inherited-caller",
        "title": "2. Method lớp cha gọi method bị override",
        "filename": "Main.java",
        "code": "\n".join((
            "class Animal {",
            '    String speak() { return "animal"; }',
            '    String introduce() { return "I say " + speak(); }',
            "}",
            "class Cat extends Animal {",
            "    @Override",
            '    String speak() { return "meow"; }',
            "}",
            "public class Main {",
            "    public static void main(String[] args) {",
            "        Animal pet = new Cat();",
            "        System.out.println(pet.introduce());",
            "    }",
            "}",
        )),
        "question": "introduce() được viết trong Animal. Khi chạy dòng 12, dòng nào được in ra?",
        "options": (
            {"id": "a", "label": "I say animal"},
            {"id": "b", "label": "Code không biên dịch vì Cat không viết introduce()"},
            {"id": "c", "label": "I say meow"},
        ),
        "correct_option": "c",
        "hints": (
            "Cat kế thừa introduce(). Khi method này chạy, this vẫn trỏ đến đối tượng nào được tạo ở dòng 11?",
            "Lời gọi speak() trong introduce() tương đương this.speak(). Lời gọi instance method đó vẫn chọn bản override theo đối tượng thực tế.",
        ),
        "explanation": "Kết quả là I say meow. Cat kế thừa introduce() từ Animal. Khi introduce() chạy trên đối tượng Cat, speak() ở dòng 3 vẫn gọi Cat.speak() ở dòng 7. Nơi viết method gọi không làm đối tượng đang chạy biến thành Animal.",
        "evidence_lines": (3, 7, 11, 12),
    },
    {
        "id": "formatter-transfer",
        "title": "3. Áp dụng với tên và cấu trúc mới",
        "filename": "Main.java",
        "code": "\n".join((
            "class Formatter {",
            '    String label() { return "base"; }',
            '    String render() { return "[" + label() + "]"; }',
            "}",
            "class LoudFormatter extends Formatter {",
            "    @Override",
            '    String label() { return "LOUD"; }',
            "}",
            "public class Main {",
            "    static String display(Formatter value) {",
            "        return value.render();",
            "    }",
            "    public static void main(String[] args) {",
            "        Formatter formatter = new LoudFormatter();",
            "        System.out.println(display(formatter));",
            "    }",
            "}",
        )),
        "question": "Đối tượng được truyền qua tham số Formatter. Chương trình in ra dòng nào?",
        "options": (
            {"id": "a", "label": "[LOUD]"},
            {"id": "b", "label": "[base]"},
            {"id": "c", "label": "Code không biên dịch vì display() là static"},
        ),
        "correct_option": "a",
        "hints": (
            "Truyền đối tượng vào tham số có kiểu lớp cha có tạo ra một đối tượng lớp cha mới không?",
            "display() là static, nhưng value.render() và label() là các lời gọi instance method trên cùng đối tượng LoudFormatter.",
        ),
        "explanation": "Kết quả là [LOUD]. Dòng 14 tạo LoudFormatter; truyền nó vào display() không đổi lớp thực tế của đối tượng. render() được kế thừa từ Formatter, nhưng label() ở dòng 3 gọi bản override ở dòng 7. Việc display() là static không biến các method của value thành static.",
        "evidence_lines": (3, 7, 10, 11, 14, 15),
    },
)
