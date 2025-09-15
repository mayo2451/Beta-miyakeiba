let currentSlide = 0;

function moveSlide(direction) {
  const items = document.querySelectorAll('.carousel-item');
  const totalSlides = items.length;

  currentSlide += direction;
  if (currentSlide < 0) currentSlide = totalSlides - 1;
  if (currentSlide >= totalSlides) currentSlide = 0;

  const offset = -currentSlide * 100;
  document.querySelector('.carousel-inner').style.transform = `translateX(${offset}%)`;
}
