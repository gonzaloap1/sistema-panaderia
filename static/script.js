document.addEventListener('DOMContentLoaded', () => {
    // Only run if we are on the index page
    const productsBody = document.getElementById('productsBody');
    if (!productsBody) return;

    const grandTotalElement = document.getElementById('grandTotal');
    const selectedCountBadge = document.getElementById('selectedCountBadge');
    const generateBtn = document.getElementById('generateBtn');
    const customerNameInput = document.getElementById('customerName');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const productsTable = document.getElementById('productsTable');
    const productSearch = document.getElementById('productSearch');
    const resetQuantitiesBtn = document.getElementById('resetQuantitiesBtn');
    const noProductsFound = document.getElementById('noProductsFound');

    // Calculate subtotal for an individual row
    function calculateRowSubtotal(row) {
        const qtyInput = row.querySelector('.qty-input');
        const priceInput = row.querySelector('.price-input');
        const subtotalCell = row.querySelector('.subtotal-cell');

        const qty = parseFloat(qtyInput.value) || 0;
        const price = parseFloat(priceInput.value) || 0;
        const subtotal = qty * price;

        subtotalCell.textContent = `$${subtotal.toFixed(2)}`;

        if (qty > 0) {
            row.classList.add('has-qty');
        } else {
            row.classList.remove('has-qty');
        }

        return { qty, price, subtotal };
    }

    // Calculate grand total & update UI indicators
    function calculateGrandTotal() {
        const rows = document.querySelectorAll('.product-row');
        let total = 0;
        let selectedCount = 0;
        let totalUnits = 0;

        rows.forEach(row => {
            const qty = parseFloat(row.querySelector('.qty-input').value) || 0;
            const price = parseFloat(row.querySelector('.price-input').value) || 0;
            
            if (qty > 0) {
                selectedCount++;
                totalUnits += qty;
                total += (qty * price);
            }
        });

        grandTotalElement.textContent = `$${total.toFixed(2)}`;

        if (selectedCount === 0) {
            selectedCountBadge.innerHTML = `<i class="fa-solid fa-basket-shopping"></i> <span>0 productos seleccionados</span>`;
            selectedCountBadge.classList.remove('active');
            generateBtn.disabled = true;
        } else {
            const unitText = totalUnits === 1 ? 'unidad' : 'unidades';
            const prodText = selectedCount === 1 ? 'producto' : 'productos';
            selectedCountBadge.innerHTML = `<i class="fa-solid fa-check-circle"></i> <span><strong>${selectedCount}</strong> ${prodText} (${totalUnits} ${unitText})</span>`;
            selectedCountBadge.classList.add('active');
            generateBtn.disabled = false;
        }
    }

    // Retrieve bread prices from JSON container safely
    let breadPrices = {};
    const breadPricesElem = document.getElementById('breadPricesData');
    if (breadPricesElem && breadPricesElem.textContent) {
        try {
            breadPrices = JSON.parse(breadPricesElem.textContent);
        } catch (e) {
            console.error('Error parsing prices JSON:', e);
        }
    }

    // Initialize all rows with prices from breadPrices if input is empty
    const allRows = document.querySelectorAll('.product-row');
    allRows.forEach(row => {
        const breadType = row.dataset.bread;
        const priceInput = row.querySelector('.price-input');
        
        if ((!priceInput.value || parseFloat(priceInput.value) === 0) && breadPrices && breadPrices[breadType]) {
            const p = parseFloat(breadPrices[breadType]);
            if (p > 0) {
                priceInput.value = p.toFixed(2);
            }
        }
        calculateRowSubtotal(row);
    });
    calculateGrandTotal();

    // Event Delegation on Products Table: +/- and Clear Row buttons
    productsTable.addEventListener('click', (e) => {
        // Handle Clear Row button (reset quantity to 0)
        const clearBtn = e.target.closest('.btn-clear-row');
        if (clearBtn) {
            const row = clearBtn.closest('tr');
            const qtyInput = row.querySelector('.qty-input');
            qtyInput.value = 0;
            calculateRowSubtotal(row);
            calculateGrandTotal();
            return;
        }

        // Handle Plus/Minus buttons
        const qtyBtn = e.target.closest('.qty-btn');
        if (qtyBtn) {
            const row = qtyBtn.closest('tr');
            const input = row.querySelector('.qty-input');
            let val = parseInt(input.value) || 0;

            if (qtyBtn.classList.contains('plus')) {
                val += 1;
            } else if (qtyBtn.classList.contains('minus')) {
                val = val > 0 ? val - 1 : 0;
            }

            input.value = val;
            calculateRowSubtotal(row);
            calculateGrandTotal();
        }
    });

    // Handle Input changes in quantities & prices
    productsTable.addEventListener('input', (e) => {
        if (e.target.classList.contains('qty-input') || e.target.classList.contains('price-input')) {
            const row = e.target.closest('tr');
            if (e.target.classList.contains('qty-input') && parseFloat(e.target.value) < 0) {
                e.target.value = 0;
            }
            calculateRowSubtotal(row);
            calculateGrandTotal();
        }
    });

    // Global reset: Reset all quantities to 0
    if (resetQuantitiesBtn) {
        resetQuantitiesBtn.addEventListener('click', () => {
            const rows = document.querySelectorAll('.product-row');
            rows.forEach(row => {
                row.querySelector('.qty-input').value = 0;
                calculateRowSubtotal(row);
            });
            calculateGrandTotal();
        });
    }

    // Search / filter products in real-time
    if (productSearch) {
        productSearch.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            const rows = document.querySelectorAll('.product-row');
            let visibleCount = 0;

            rows.forEach(row => {
                const breadName = (row.dataset.bread || '').toLowerCase();
                if (!query || breadName.includes(query)) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });

            if (visibleCount === 0) {
                noProductsFound.classList.remove('hidden');
            } else {
                noProductsFound.classList.add('hidden');
            }
        });
    }

    // Generate Invoice handler
    generateBtn.addEventListener('click', async () => {
        const rows = document.querySelectorAll('.product-row');
        const items = [];
        let priceErrorBread = null;
        let priceErrorInput = null;

        rows.forEach(row => {
            const qty = parseFloat(row.querySelector('.qty-input').value) || 0;
            const priceInput = row.querySelector('.price-input');
            const price = parseFloat(priceInput.value) || 0;
            const breadType = row.dataset.bread;

            if (qty > 0) {
                if (price <= 0) {
                    if (!priceErrorBread) {
                        priceErrorBread = breadType;
                        priceErrorInput = priceInput;
                    }
                } else {
                    items.push({
                        bread_type: breadType,
                        quantity: qty,
                        unit_price: price,
                        total_price: qty * price
                    });
                }
            }
        });

        if (priceErrorBread) {
            alert(`Por favor, ingresa un precio unitario válido mayor a 0 para "${priceErrorBread}".`);
            if (priceErrorInput) {
                priceErrorInput.focus();
                priceErrorInput.select();
            }
            return;
        }

        if (items.length === 0) {
            alert('Por favor, indica una cantidad mayor a 0 para al menos un producto.');
            return;
        }

        const customerName = customerNameInput.value.trim() || 'Consumidor Final';

        loadingOverlay.classList.remove('hidden');

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    customer_name: customerName,
                    items: items
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Error al generar la factura');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);

            const disposition = response.headers.get('Content-Disposition');
            let filename = 'factura.png';
            if (disposition && disposition.indexOf('attachment') !== -1) {
                const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                const matches = filenameRegex.exec(disposition);
                if (matches != null && matches[1]) {
                    filename = matches[1].replace(/['"]/g, '');
                }
            }

            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();

            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            // Reset quantities for a new order while keeping all products on screen
            rows.forEach(row => {
                row.querySelector('.qty-input').value = 0;
                calculateRowSubtotal(row);
            });
            calculateGrandTotal();
            customerNameInput.value = '';

            // Reset search filter if any
            if (productSearch) {
                productSearch.value = '';
                rows.forEach(row => row.style.display = '');
                noProductsFound.classList.add('hidden');
            }

        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    });
});
