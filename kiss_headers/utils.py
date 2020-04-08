from typing import List, Type, Optional, Iterable, Tuple, Any
from re import findall
from email.header import decode_header


def normalize_str(string: str) -> str:
    """
    Normalize a string by applying on it lowercase and replacing '-' to '_'.
    """
    return string.lower().replace("-", "_")


def extract_class_name(type_: Type) -> Optional[str]:
    """
    Typically extract a class name from a Type.
    """
    r = findall(r"<class '([a-zA-Z0-9._]+)'>", str(type_))
    return r[0] if r else None


def flat_split(string: str, delimiter: str) -> List[str]:
    """
    Take a string and split it according to the passed delimiter.
    It will ignore delimiter if inside between double quote or inside a value.
    The input string is considered perfectly formed.
    """
    if len(delimiter) != 1 or delimiter == '"':
        raise ValueError(
            "Delimiter cannot be a double quote nor it can be longer than 1 char."
        )

    in_double_quote: bool = False
    in_value: bool = False
    result: List[str] = [""]

    for letter, index in zip(string, range(0, len(string))):

        if letter == '"':
            in_double_quote = not in_double_quote

            if in_value and not in_double_quote:
                in_value = False

        if not in_double_quote:

            if not in_value and letter == "=":
                in_value = True
            elif letter == ";" and in_value:
                in_value = False

            if (
                in_value
                and letter == delimiter
                and index > 3
                and string[index - 3 : index]
                not in {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
            ):
                in_value = False

        if letter == delimiter and ((in_value or in_double_quote) is False):

            result[-1] = result[-1].lstrip().rstrip()
            result.append("")

            continue

        result[-1] += letter

    if result:
        result[-1] = result[-1].lstrip().rstrip()

    return result


def class_to_header_name(type_: Type) -> str:
    """
    Take a type and infer its header name.
    """
    class_raw_name: str = str(type_).split("'")[-2].split(".")[-1]

    if class_raw_name.endswith("_"):
        class_raw_name = class_raw_name[:-1]

    if class_raw_name.startswith("_"):
        class_raw_name = class_raw_name[1:]

    header_name: str = str()

    for letter in class_raw_name:
        if letter.isupper() and header_name != "":
            header_name += "-" + letter
            continue
        header_name += letter

    return header_name


def header_name_to_class(name: str, root_type: Type) -> Type:
    """
    The opposite of class_to_header_name function. Will raise TypeError if no corresponding entry is found.
    Do it recursively from the root type.
    """

    normalized_name = normalize_str(name).replace("_", "")

    for subclass in root_type.__subclasses__():
        class_name = extract_class_name(subclass)

        if class_name is None:
            continue

        if normalize_str(class_name.split(".")[-1]) == normalized_name:
            return subclass

        if subclass.__subclasses__():
            try:
                return header_name_to_class(name, subclass)
            except TypeError:
                continue

    raise TypeError(
        "Cannot find a class matching header named '{name}'.".format(name=name)
    )


def prettify_header_name(name: str) -> str:
    """
    Take a header name and prettify it.
       >>> prettify_header_name("x-hEllo-wORLD")
       X-Hello-World
       >>> prettify_header_name("server")
       Server
       >>> prettify_header_name("contEnt-TYPE")
       Content-Type
       >>> prettify_header_name("content_type")
       Content-Type
    """
    return "-".join([el.capitalize() for el in name.replace("_", "-").split("-")])


def decode_partials(items: Iterable[Tuple[str, Any]]) -> List[Tuple[str, str]]:
    """
    This function takes a list of tuple, representing headers by key, value. Where value is bytes or string containing
    (RFC 2047 encoded) partials fragments like the following :
       >>> decode_partials([("Subject", b"=?iso-8859-1?q?p=F6stal?=")])
       [("Subject", "pöstal")]
    """
    revised_items: List[Tuple[str, str]] = list()

    for head, content in items:
        revised_content: str = str()

        for partial, partial_encoding in decode_header(content):
            if isinstance(partial, str):
                revised_content += partial
            if isinstance(partial, bytes):
                revised_content += partial.decode(
                    partial_encoding if partial_encoding is not None else "utf-8",
                    errors="ignore",
                )

        revised_items.append((head, revised_content))

    return revised_items


def unquote(string: str) -> str:
    """
    Remove simple quote or double quote around a string if any.
       >>> unquote('"hello"')
       'hello'
       >>> unquote('"hello')
       '"hello'
       >>> unquote('"a"')
       ''
       >>> unquote('""')
       ''
    """
    if len(string) >= 2 and (string.startswith('"') and string.endswith('"')) or (string.startswith("'") and string.endswith("'")):
        return string[1:-1]

    return string
