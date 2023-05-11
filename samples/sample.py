import random


class Author:
    def __init__(self, name):
        self.name = name
        self.books = []

    def write_book(self, title, num_pages):
        book = Book(title, self, num_pages)
        self.books.append(book)
        return book

    def __str__(self):
        return self.name


class Book:
    def __init__(self, title, author, num_pages):
        self.title = title
        self.author = author
        self.num_pages = num_pages

    def __str__(self):
        return f"'{self.title}' by {self.author}"


class BookStore:
    def __init__(self, name):
        self.name = name
        self.books = []

    def add_book(self, book):
        self.books.append(book)

    def display_books(self):
        for book in self.books:
            print(book)

    def __str__(self):
        return self.name


def create_authors(names):
    authors = []
    for name in names:
        authors.append(Author(name))
    return authors


def simulate_book_writing(authors, num_books):
    for _ in range(num_books):
        author = random.choice(authors)
        num_pages = random.randint(100, 1000)
        title = f"Book {random.randint(1, 1000)}"
        book = author.write_book(title, num_pages)
        print(f"New book written: {book}")
        return book


def simulate_bookstore(authors, num_books):
    store = BookStore("The Great Bookstore")
    for _ in range(num_books):
        book = simulate_book_writing(authors, 1)
        store.add_book(book)
    print(f"\nBooks at {store}:")
    store.display_books()


def main():
    authors = create_authors(["Alice", "Bob", "Charlie"])
    simulate_bookstore(authors, 5)


if __name__ == "__main__":
    main()