window.addEventListener('chainlit-custom-element', (e) => {
    const { name, props } = e.detail;
    
    // Слушаем специальный слой отображения интерфейса
    if (name === "dynamic-html-layer") {
        const { htmlMarkup } = props;
        if (!htmlMarkup) return;

        // Ищем или создаем изолированный viewport для 2/3 экрана
        let container = document.getElementById("runtime-viewport-23");
        if (!container) {
            container = document.createElement("div");
            container.id = "runtime-viewport-23";
            document.body.appendChild(container);
        }

        // Инжектируем чистый HTML/CSS, сгенерированный Эйрой
        container.innerHTML = htmlMarkup;
    }
});
